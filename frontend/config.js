// raid-fun — environment config
// Auto-detects local dev vs production.
window.RAID_API = (
  window.location.hostname === 'localhost' ||
  window.location.hostname === '127.0.0.1'
)
  ? 'http://localhost:8000'
  : 'https://raid-fun.onrender.com';
