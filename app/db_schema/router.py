from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import inspect as sa_inspect, text

from app.database import get_engine

BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()


@router.get("/schema", include_in_schema=False)
async def schema_page(request: Request):
    return templates.TemplateResponse(request=request, name="dev_database.html")


class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool
    default: str | None
    is_pk: bool
    fk_ref: str | None


class IndexInfo(BaseModel):
    name: str | None
    column_names: list[str]
    unique: bool


class TableInfo(BaseModel):
    name: str
    columns: list[ColumnInfo]
    indexes: list[IndexInfo]
    row_count: int
    sample_rows: list[dict]
    col_names: list[str]


class SchemaResponse(BaseModel):
    tables: list[TableInfo]
    total_tables: int
    total_rows: int
    total_columns: int


@router.get("/api/schema", response_model=SchemaResponse)
async def get_schema():
    engine = get_engine()
    inspector = sa_inspect(engine)
    tables: list[TableInfo] = []
    total_rows = 0
    total_columns = 0

    for table_name in sorted(inspector.get_table_names()):
        columns = inspector.get_columns(table_name)
        pk = inspector.get_pk_constraint(table_name)
        fks = inspector.get_foreign_keys(table_name)
        indexes = inspector.get_indexes(table_name)

        pk_cols = set(pk.get("constrained_columns", []))
        fk_map: dict[str, str] = {}
        for fk in fks:
            for i, col in enumerate(fk["constrained_columns"]):
                ref_col = fk["referred_columns"][i]
                fk_map[col] = f'{fk["referred_table"]}.{ref_col}'

        with engine.connect() as conn:
            row_count = conn.execute(
                text(f'SELECT COUNT(*) FROM "{table_name}"')
            ).scalar()
            result = conn.execute(
                text(f'SELECT * FROM "{table_name}" LIMIT 10')
            )
            sample_rows = [
                {k: _serialise(v) for k, v in row._mapping.items()}
                for row in result
            ]

        col_names = [c["name"] for c in columns]
        total_rows += row_count
        total_columns += len(columns)

        enriched_columns = [
            ColumnInfo(
                name=col["name"],
                type=str(col["type"]),
                nullable=col.get("nullable", True),
                default=col.get("default"),
                is_pk=col["name"] in pk_cols,
                fk_ref=fk_map.get(col["name"]),
            )
            for col in columns
        ]

        tables.append(TableInfo(
            name=table_name,
            columns=enriched_columns,
            indexes=[
                IndexInfo(
                    name=idx.get("name"),
                    column_names=idx.get("column_names", []),
                    unique=idx.get("unique", False),
                )
                for idx in indexes
            ],
            row_count=row_count,
            sample_rows=sample_rows,
            col_names=col_names,
        ))

    return SchemaResponse(
        tables=tables,
        total_tables=len(tables),
        total_rows=total_rows,
        total_columns=total_columns,
    )


def _serialise(value: object) -> object:
    """Ensure all values are JSON-serialisable."""
    if value is None:
        return None
    if isinstance(value, (int, float, bool)):
        return value
    return str(value)
