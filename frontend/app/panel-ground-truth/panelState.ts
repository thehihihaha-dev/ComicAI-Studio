export type PanelBox = { panel_id: string; bbox: [number, number, number, number]; ambiguous: boolean };
export type Size = { width: number; height: number };
export type DisplayRect = { left: number; top: number; width: number; height: number };

export function renderedImageRect(surface: Size, source: Size): DisplayRect {
  if (surface.width <= 0 || surface.height <= 0 || source.width <= 0 || source.height <= 0) {
    return { left: 0, top: 0, width: 0, height: 0 };
  }
  const scale = Math.min(surface.width / source.width, surface.height / source.height);
  const width = source.width * scale, height = source.height * scale;
  return { left: (surface.width - width) / 2, top: (surface.height - height) / 2, width, height };
}

export function pointerToSource(
  point: [number, number], surface: Size, source: Size,
): [number, number] | null {
  const image = renderedImageRect(surface, source), [x, y] = point;
  if (image.width === 0 || image.height === 0 || x < image.left || x > image.left + image.width
      || y < image.top || y > image.top + image.height) return null;
  return [(x - image.left) / image.width * source.width, (y - image.top) / image.height * source.height];
}

export function sourceBoxToDisplay(box: PanelBox["bbox"], surface: Size, source: Size): PanelBox["bbox"] {
  const image = renderedImageRect(surface, source);
  return [image.left + box[0] / source.width * image.width, image.top + box[1] / source.height * image.height,
    image.left + box[2] / source.width * image.width, image.top + box[3] / source.height * image.height];
}

export function drawnBox(start: [number, number], end: [number, number]): PanelBox["bbox"] {
  return [Math.min(start[0],end[0]),Math.min(start[1],end[1]),Math.max(start[0],end[0]),Math.max(start[1],end[1])];
}
export function movedBox(box: PanelBox["bbox"], dx:number, dy:number, width:number, height:number): PanelBox["bbox"] {
  const boxWidth=box[2]-box[0],boxHeight=box[3]-box[1],x1=Math.max(0,Math.min(width-boxWidth,box[0]+dx)),y1=Math.max(0,Math.min(height-boxHeight,box[1]+dy));
  return [x1,y1,x1+boxWidth,y1+boxHeight];
}
export function resizedBox(box:PanelBox["bbox"],corner:string,point:[number,number]):PanelBox["bbox"] {
  const next:[number,number,number,number]=[...box];if(corner.includes("l"))next[0]=Math.min(point[0],next[2]-2);if(corner.includes("r"))next[2]=Math.max(point[0],next[0]+2);if(corner.includes("t"))next[1]=Math.min(point[1],next[3]-2);if(corner.includes("b"))next[3]=Math.max(point[1],next[1]+2);return next;
}
export function toggledAmbiguity(boxes:PanelBox[],id:string):PanelBox[]{return boxes.map(box=>box.panel_id===id?{...box,ambiguous:!box.ambiguous}:box);}
export function deletedBox(boxes:PanelBox[],id:string):PanelBox[]{return boxes.filter(box=>box.panel_id!==id);}
export function navigatedIndex(current:number,delta:number,total:number):number{return Math.max(0,Math.min(total-1,current+delta));}
