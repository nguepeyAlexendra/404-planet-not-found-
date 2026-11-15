export const tileUrl = (key: string, date: string, demo: boolean, mode: "amplitude" | "classes" = "amplitude") =>
  `/api/v1/tiles/${key}/${date}/{z}/{x}/{y}.png?mode=${mode}&demo=${demo ? 1 : 0}`;
export const changeTileUrl = (key: string, a: string, b: string, demo: boolean, threshold: number) =>
  `/api/v1/tiles/change/${key}/${a}/${b}/{z}/{x}/{y}.png?demo=${demo ? 1 : 0}&threshold_db=${threshold}`;
