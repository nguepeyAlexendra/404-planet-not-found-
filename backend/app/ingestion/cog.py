"""Écriture de COG (avec overviews) depuis un tableau et une grille."""
from pathlib import Path

import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from rio_cogeo.cogeo import cog_translate, cog_validate
from rio_cogeo.profiles import cog_profiles


def write_cog(array: np.ndarray, x: np.ndarray, y: np.ndarray, epsg: int, out: Path,
              nodata: float | None = None) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    px, py = abs(float(x[1] - x[0])), abs(float(y[1] - y[0]))
    transform = from_origin(float(x.min()) - px / 2, float(y.max()) + py / 2, px, py)
    data = array.astype("float32")
    nd = float("nan") if nodata is None else nodata
    profile = dict(driver="GTiff", height=data.shape[0], width=data.shape[1], count=1, dtype="float32",
                   crs=f"EPSG:{epsg}", transform=transform, nodata=nd)
    with MemoryFile() as mem:
        with mem.open(**profile) as dst:
            dst.write(data, 1)
        with mem.open() as src:
            cog_translate(src, str(out), cog_profiles.get("deflate"), quiet=True, nodata=nd, overview_resampling="average")
    ok, errors, _ = cog_validate(str(out))
    if not ok:
        raise RuntimeError(f"COG invalide : {errors}")
    return out


def raster_info(path: Path) -> dict:
    with rasterio.open(path) as src:
        return {"width": src.width, "height": src.height, "crs": str(src.crs), "nodata": src.nodata,
                "dtype": src.dtypes[0], "bounds": tuple(src.bounds), "res": src.res}
