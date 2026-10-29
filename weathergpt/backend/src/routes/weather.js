const router = require('express').Router();
const axios = require('axios');

// GET /api/weather/current?lat=&lon=
router.get('/current', async (req, res) => {
  try {
    const { lat, lon, location } = req.query;
    const response = await axios.get(`${process.env.DATA_SERVICE_URL}/weather/current`, {
      params: { lat, lon, location }
    });
    res.json(response.data);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/weather/forecast?lat=&lon=&days=
router.get('/forecast', async (req, res) => {
  try {
    const { lat, lon, days, location } = req.query;
    const response = await axios.get(`${process.env.DATA_SERVICE_URL}/weather/forecast`, {
      params: { lat, lon, days, location }
    });
    res.json(response.data);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
