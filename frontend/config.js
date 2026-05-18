// raid-fun — environment config
// Auto-detects local dev vs production.
// For production: replace the URL below with your Render backend URL.
window.RAID_API = (
  window.location.hostname === 'localhost' ||
  window.location.hostname === '127.0.0.1'
)
  ? 'http://localhost:8000'
  : 'https://REPLACE_WITH_YOUR_RENDER_URL.onrender.com';
