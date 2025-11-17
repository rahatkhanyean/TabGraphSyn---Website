from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from pandas.api.types import (
    is_bool_dtype,
    is_datetime64_any_dtype,
    is_integer_dtype,
    is_numeric_dtype,
)


@dataclass
class ColumnMetadata:
    name: str
    kind: str
    is_integer: bool = False
    allow_missing: bool = False
    minimum: float | None = None
    maximum: float | None = None


class SyntheticPipeline:
    """Lightweight tabular data synthesiser used by the Django app."""

    def __init__(self, random_state: int | None = None):
        self._rng = np.random.default_rng(random_state)

    def generate(self, df: pd.DataFrame, rows: int | None = None) -> pd.DataFrame:
        if df.empty:
            raise ValueError('Uploaded dataset must contain at least one row.')

        target_rows = rows or len(df)
        if target_rows <= 0:
            raise ValueError('Number of synthetic rows must be a positive integer.')

        metadata = self._build_metadata(df)
        synthetic_columns: dict[str, Any] = {}

        for column_meta in metadata:
            series = df[column_meta.name]
            if column_meta.kind == 'numeric':
                synthetic_columns[column_meta.name] = self._sample_numeric(series, column_meta, target_rows)
            elif column_meta.kind == 'categorical':
                synthetic_columns[column_meta.name] = self._sample_categorical(series, column_meta, target_rows)
            elif column_meta.kind == 'datetime':
                synthetic_columns[column_meta.name] = self._sample_datetime(series, column_meta, target_rows)
            else:
                raise ValueError(f'Unsupported column type: {column_meta.kind}')

        return pd.DataFrame(synthetic_columns, columns=df.columns)

    def _build_metadata(self, df: pd.DataFrame) -> list[ColumnMetadata]:
        metadata: list[ColumnMetadata] = []
        for column in df.columns:
            series = df[column]
            allow_missing = series.isna().any()

            if is_datetime64_any_dtype(series):
                metadata.append(ColumnMetadata(name=column, kind='datetime', allow_missing=allow_missing))
                continue

            if is_bool_dtype(series):
                metadata.append(ColumnMetadata(name=column, kind='categorical', allow_missing=allow_missing))
                continue

            if is_numeric_dtype(series):
                series_no_na = series.dropna()
                minimum = float(series_no_na.min()) if not series_no_na.empty else None
                maximum = float(series_no_na.max()) if not series_no_na.empty else None
                is_int = is_integer_dtype(series_no_na.dtype) if not series_no_na.empty else False
                if not is_int and not series_no_na.empty:
                    is_int = np.allclose(series_no_na, np.round(series_no_na))
                metadata.append(
                    ColumnMetadata(
                        name=column,
                        kind='numeric',
                        is_integer=is_int,
                        allow_missing=allow_missing,
                        minimum=minimum,
                        maximum=maximum,
                    )
                )
                continue

            metadata.append(ColumnMetadata(name=column, kind='categorical', allow_missing=allow_missing))
        return metadata

    def _sample_numeric(self, series: pd.Series, meta: ColumnMetadata, rows: int) -> pd.Series:
        available = series.dropna().astype(float)
        if available.empty:
            result = pd.Series(np.full(rows, np.nan), dtype='float64')
        elif len(np.unique(available)) == 1:
            result = pd.Series(np.full(rows, available.iloc[0]), dtype='float64')
        else:
            mean = float(available.mean())
            std = float(available.std(ddof=0))
            if std < 1e-6:
                std = max(abs(mean) * 0.05, 1.0)
            sampled = self._rng.normal(mean, std, size=rows)
            if meta.minimum is not None and meta.maximum is not None:
                lower = meta.minimum - abs(meta.minimum) * 0.05
                upper = meta.maximum + abs(meta.maximum) * 0.05
                sampled = np.clip(sampled, lower, upper)
            result = pd.Series(sampled, dtype='float64')

        result = self._apply_missing_mask(series, result)

        if meta.is_integer:
            return result.round().astype('Int64')
        return result

    def _sample_categorical(self, series: pd.Series, meta: ColumnMetadata, rows: int) -> pd.Series:
        available = series.dropna()
        if available.empty:
            result = pd.Series([np.nan] * rows, dtype='object')
        else:
            freq = available.value_counts(normalize=True)
            categories = freq.index.to_numpy()
            probabilities = freq.to_numpy()
            sampled = self._rng.choice(categories, size=rows, p=probabilities)
            result = pd.Series(sampled)

        result = self._apply_missing_mask(series, result)
        try:
            return result.astype(series.dtype)
        except (TypeError, ValueError):
            return result

    def _sample_datetime(self, series: pd.Series, meta: ColumnMetadata, rows: int) -> pd.Series:
        available = series.dropna()
        if available.empty:
            result = pd.Series([pd.NaT] * rows, dtype='datetime64[ns]')
        else:
            timestamps = available.view('int64')
            if len(np.unique(timestamps)) == 1:
                sampled = np.full(rows, timestamps.iloc[0])
            else:
                mean = float(timestamps.mean())
                std = float(timestamps.std(ddof=0))
                if std < 1:
                    std = 86_400_000_000_000  # one day in nanoseconds
                sampled = self._rng.normal(mean, std, size=rows)
                sampled = np.clip(sampled, timestamps.min(), timestamps.max())
            result = pd.Series(pd.to_datetime(sampled.astype('int64')))

        result = self._apply_missing_mask(series, result)
        return result.astype(series.dtype)

    def _apply_missing_mask(self, original: pd.Series, data: pd.Series) -> pd.Series:
        missing_rate = original.isna().mean()
        if missing_rate <= 0:
            return data
        mask = self._rng.random(len(data)) < missing_rate
        result = data.copy()
        fill_value = pd.NA if is_integer_dtype(result.dtype) else np.nan
        result.loc[mask] = fill_value
        return result


def run_pipeline(dataset: pd.DataFrame, rows: int | None = None, seed: int | None = None) -> pd.DataFrame:
    """Convenience wrapper used by the Django view."""
    generator = SyntheticPipeline(random_state=seed)
    return generator.generate(dataset, rows=rows)
