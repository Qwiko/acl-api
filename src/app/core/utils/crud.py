from typing import Any, Dict, Generic, List, Optional, Tuple, Type, TypeVar

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import asc, desc, func, inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload, noload

from app.core.exceptions.http_exceptions import NotFoundException

T = TypeVar("T")  # Represents a SQLAlchemy model
P = TypeVar("P", bound=BaseModel)  # Represents a Pydantic model


async def paginate_query_with_range(
    db: AsyncSession,
    model: Type[T],
    start: int,
    end: int,
    load_relations: bool = False,
    filter_by: Optional[Dict[str, Any]] = None,
    sort: Optional[List[str]] = None,
    q_field: str = "name",  # Default search field
) -> Tuple[List[T], int]:
    """
    Fetch records based on a range (start-end) and return the total count.
    """

    # Start building the base query
    stmt = select(model)
    total_count_stmt = select(func.count()).select_from(model)

    if not load_relations:
        stmt = stmt.options(noload("*"))

    # if load_relations:
    #     # relationships = [rel.key for rel in inspect(model).relationships]
    #     # stmt = stmt.options(*(selectinload(getattr(model, rel)) for rel in relationships))
    #     stmt = stmt.options(selectinload("*"))
    #                 # Apply filters if provided
    # Get model columns dynamically
    model_columns = {column.name: column for column in inspect(model).c}

    # Apply filters if provided
    filters = []
    if filter_by:
        for field, value in filter_by.items():
            if field == "q" and q_field in model_columns:  # Handle full-text search on 'q_field'
                column = model_columns[q_field]
                filters.append(column.ilike(f"%{value}%"))
            elif field in model_columns:
                column = model_columns[field]
                if isinstance(value, list):  # Handle IN clause
                    filters.append(column.in_(value))
                else:  # Handle exact match
                    filters.append(column == value)

    if filters:
        stmt = stmt.where(*filters)
        total_count_stmt = total_count_stmt.where(*filters)

    # Apply sorting if provided
    if sort:
        sort_field, sort_order = sort
        sort_column = getattr(model, sort_field, None)
        if sort_column is not None:
            stmt = stmt.order_by(asc(sort_column) if sort_order.upper() == "ASC" else desc(sort_column))

    # Apply pagination
    stmt = stmt.offset(start).limit(end - start + 1)

    # Execute queries
    total_count = await db.scalar(total_count_stmt)
    result = await db.execute(stmt)

    return result.unique().scalars().all(), total_count


class BaseCRUD(Generic[T]):
    def __init__(self, model: Type[T]):
        self.model = model

    async def get(self, db: AsyncSession, obj_id: int, load_relations: bool = False, filter_by: Optional[Dict] = None):
        stmt = select(self.model).where(self.model.id == obj_id)
        # if load_relations:
        #     # relationships = [rel.key for rel in inspect(self.model).relationships]
        #     # stmt = stmt.options(*(selectinload(getattr(self.model, rel)) for rel in relationships))
        #     stmt = stmt.options(selectinload("*"))

        filters = []

        # Apply filters if provided
        if filter_by:
            model_columns = {column.name: column for column in inspect(self.model).c}
            for field, value in filter_by.items():
                if field in model_columns:
                    column = model_columns[field]
                    if isinstance(value, list):  # Handle IN clause
                        filters.append(column.in_(value))
                    else:  # Handle exact match
                        filters.append(column == value)
        if filters:
            stmt = stmt.where(*filters)

        result = await db.execute(stmt)
        return result.unique().scalars().one_or_none()

    async def get_paginated_with_range(
        self,
        db: AsyncSession,
        start: int,
        end: int,
        load_relations: bool = False,
        filter_by: Optional[Dict] = None,
        sort: Optional[List[str]] = None,
        q_field: str = "name",  # Default search field
    ):
        return await paginate_query_with_range(db, self.model, start, end, load_relations, filter_by, sort, q_field)

    async def get_all(self, db: AsyncSession, load_relations: bool = False, filter_by: Optional[Dict] = None):
        stmt = select(self.model)
        # if load_relations:
        #     relationships = [rel.key for rel in inspect(self.model).relationships]
        #     # stmt = stmt.options(*(selectinload(getattr(self.model, rel)) for rel in relationships))
        #     stmt = stmt.options(selectinload("*"))
        #             # Apply filters if provided
        filters = []

        # Apply filters if provided
        if filter_by:
            model_columns = {column.name: column for column in inspect(self.model).c}
            for field, value in filter_by.items():
                if field in model_columns:
                    column = model_columns[field]
                    if isinstance(value, list):  # Handle IN clause
                        filters.append(column.in_(value))
                    else:  # Handle exact match
                        filters.append(column == value)
        if filters:
            stmt = stmt.where(*filters)

        result = await db.execute(stmt)
        return result.unique().scalars().all()

    async def create(self, db: AsyncSession, obj_data: P, extra_data: Optional[Dict] = None):
        """Create a new record with optional additional parameters."""

        # Convert Pydantic model to dict
        data_dict = obj_data.model_dump()

        many_to_many_data = {}

        # Merge extra_data if provided
        if extra_data:
            data_dict.update(extra_data)

        for field, value in data_dict.items():
            if isinstance(value, list) and all(isinstance(item, int) for item in value):
                many_to_many_data[field] = value

        for field in many_to_many_data.keys():
            data_dict[field] = []  # Remove M2M fields from update_dict

        new_obj = self.model(**data_dict)

        db.add(new_obj)
        await db.commit()
        await db.refresh(new_obj)

        # Update M2M relationships
        for field, related_ids in many_to_many_data.items():
            await self._update_m2m_relationship(db, new_obj, field, related_ids)

        return new_obj

    async def update(self, db: AsyncSession, obj_id: int, update_data: P, extra_data: Optional[Dict] = None) -> T:
        """Update a record using a Pydantic model, including handling M2M relationships."""

        stmt = select(self.model).where(self.model.id == obj_id)
        stmt = stmt.options(selectinload("*"))
        result = await db.execute(stmt)
        obj = result.scalars().first()

        if not obj:
            raise HTTPException(status_code=404, detail=f"{self.model.__name__} not found")

        update_dict = update_data.model_dump(exclude_unset=True)
        many_to_many_data = {}

        # Merge extra_data if provided
        if extra_data:
            update_dict.update(extra_data)

        for field, value in update_dict.items():
            if isinstance(value, list) and all(isinstance(item, int) for item in value):
                many_to_many_data[field] = value

        for field in many_to_many_data.keys():
            del update_dict[field]  # Remove M2M fields from update_dict

        for key, value in update_dict.items():
            setattr(obj, key, value)

        await db.commit()
        await db.refresh(obj)

        # Update M2M relationships
        for field, related_ids in many_to_many_data.items():
            await self._update_m2m_relationship(db, obj, field, related_ids)

        return obj

    async def _update_m2m_relationship(self, db: AsyncSession, obj: T, field: str, related_ids: list):
        """Update many-to-many relationships, ensuring the objects exist before adding."""
        related_attr = getattr(self.model, field)

        related_model = related_attr.property.mapper.class_

        # Fetch related objects based on provided IDs
        stmt = select(related_model).where(related_model.id.in_(related_ids))
        result = await db.execute(stmt)
        related_objects = result.unique().scalars().all()

        if len(related_objects) != len(related_ids):
            raise HTTPException(status_code=400, detail=f"Some related objects for {field} do not exist")

        setattr(obj, field, related_objects)
        await db.commit()
        await db.refresh(obj)

    async def delete(self, db: AsyncSession, obj_id: int):
        stmt = select(self.model).where(self.model.id == obj_id)
        result = await db.execute(stmt)
        obj = result.scalars().first()
        if not obj:
            raise NotFoundException(f"{self.model.__name__} with ID {obj_id} not found")

        await db.delete(obj)
        await db.commit()
        return obj
