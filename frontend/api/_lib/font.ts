let fontCache: ArrayBuffer | null = null;

export async function loadFont(): Promise<ArrayBuffer> {
  if (fontCache) return fontCache;

  const res = await fetch(
    'https://fonts.gstatic.com/s/inter/v18/UcCo3FwrK3iLTcviYwY.ttf'
  );
  fontCache = await res.arrayBuffer();
  return fontCache;
}
