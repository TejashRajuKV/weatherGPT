const router = require('express').Router();
const auth = require('../middleware/auth');
const Alert = require('../models/Alert');
const User = require('../models/User');

const isAdmin = (req, res, next) => {
  if (req.user.role !== 'admin') return res.status(403).json({ error: 'Admin only' });
  next();
};

// POST /api/admin/alerts - create alert
router.post('/alerts', auth, isAdmin, async (req, res) => {
  try {
    const alert = await Alert.create(req.body);
    res.json(alert);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/admin/alerts - all alerts
router.get('/alerts', auth, isAdmin, async (req, res) => {
  try {
    const alerts = await Alert.find().sort({ created_at: -1 });
    res.json(alerts);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/admin/users - user list
router.get('/users', auth, isAdmin, async (req, res) => {
  try {
    const users = await User.find().select('-password');
    res.json(users);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// PATCH /api/admin/alerts/:id - update alert status
router.patch('/alerts/:id', auth, isAdmin, async (req, res) => {
  try {
    const alert = await Alert.findByIdAndUpdate(req.params.id, req.body, { new: true });
    res.json(alert);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
