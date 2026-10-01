// Drawing notes on the map.
import type { Pin } from '../types';

/** Note being drawn: shape and the points placed so far (world metres) */
export interface Draft { shape: Pin['shape']; pts: number[][] }
/** Points a shape needs before it can be saved */
export const minPoints = (shape: Draft['shape']) => (shape === 'point' ? 1 : shape === 'line' ? 2 : 3);
