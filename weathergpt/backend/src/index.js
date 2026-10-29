require('dotenv').config({ path: require('path').join(__dirname, '../../.env') });
const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const rateLimit = require('express-rate-limit');
const { createServer } = require('http');
const WebSocket = require('ws');
const mongoose = require('mongoose');

const authRoutes = require('./routes/auth');
const chatRoutes = require('./routes/chat');
const weatherRoutes = require('./routes/weather');
const alertRoutes = require('./routes/alerts');
const voiceRoutes = require('./routes/voice');
const climateRoutes = require('./routes/climate');
const adminRoutes = require('./routes/admin');

const app = express();
const server = createServer(app);
const wss = new WebSocket.Server({ server, path: '/ws/chat' });

// Middleware
app.use(helmet());
app.use(cors());
app.use(express.json());
app.use(rateLimit({ windowMs: 60 * 1000, max: 60 }));

// Routes
app.use('/api/auth', authRoutes);
app.use('/api/chat', chatRoutes);
app.use('/api/weather', weatherRoutes);
app.use('/api/alerts', alertRoutes);
app.use('/api/voice', voiceRoutes);
app.use('/api/climate', climateRoutes);
app.use('/api/admin', adminRoutes);

app.get('/health', (req, res) => res.json({ status: 'ok' }));

// WebSocket - stream chat responses
wss.on('connection', (ws) => {
  console.log('WebSocket client connected');
  ws.on('message', async (data) => {
    try {
      const { query, location, language, conversationId } = JSON.parse(data);
      const axios = require('axios');
      const response = await axios.post(`${process.env.AI_SERVICE_URL}/chat`, {
        query, location, language, conversationId
      });
      ws.send(JSON.stringify({ type: 'response', data: response.data }));
    } catch (err) {
      ws.send(JSON.stringify({ type: 'error', message: err.message }));
    }
  });
  ws.on('close', () => console.log('WebSocket client disconnected'));
});

// MongoDB
mongoose.connect(process.env.MONGODB_URI)
  .then(() => console.log('MongoDB connected'))
  .catch(err => console.error('MongoDB error:', err));

const PORT = process.env.PORT || 4000;
server.listen(PORT, () => console.log(`Backend running on port ${PORT}`));
