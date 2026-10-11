export function GET() {
  return new Response(null, {
    status: 204,
    headers: {
      'Content-Type': 'image/x-icon',
      'Cache-Control': 'public, max-age=0, must-revalidate',
    },
  });
}
