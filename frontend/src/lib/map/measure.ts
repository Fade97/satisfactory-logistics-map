// Measuring on the map: distance along the points, straight line, enclosed area, building material.
import { fmtNum } from '../fmt';

export interface MeasureStats {
  len: number; direct: number; area: number;          // metres / m² (area only from 3 points)
  rails: number; belts: number; foundations: number;  // pieces: rail 12 m, belt max. 56 m, foundation 8×8 m
}

export function measureStats(pts: number[][] | null): MeasureStats | null {
  if (!pts || pts.length < 2) return null;
  let len = 0;
  for (let i = 1; i < pts.length; i++) len += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
  let area = 0;
  if (pts.length >= 3) {                             // shoelace formula, polygon closed back to the start
    for (let i = 0; i < pts.length; i++) { const a = pts[i], b = pts[(i + 1) % pts.length]; area += a[0] * b[1] - b[0] * a[1]; }
    area = Math.abs(area) / 2;
  }
  const first = pts[0], last = pts[pts.length - 1];
  return { len, area, direct: Math.hypot(last[0] - first[0], last[1] - first[1]),
           rails: Math.ceil(len / 12), belts: Math.ceil(len / 56), foundations: Math.floor(area / 64) };
}

/** Area: "1,234 m²", "2.50 km²" */
export const fmtArea = (a: number) => (a >= 1e6 ? (a / 1e6).toFixed(2) + ' km²' : fmtNum(Math.round(a)) + ' m²');
