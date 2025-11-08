# Personal Finance App - Mobile

React Native mobile app built with Expo for the Personal Finance App.

## Features

- **Authentication**: Secure login and registration with Supabase
- **AI Chat Interface**: Voice and text-based financial assistance
- **Financial Entries**: View and manage income/expense entries
- **Real-time Sync**: Data syncs with web app and backend
- **Voice Recording**: Record voice messages for AI processing

## Setup

1. **Install dependencies**:

   ```bash
   npm install
   ```

2. **Configure environment**:

   - Copy `.env.example` to `.env`
   - Update API URLs for your environment
   - For local development, use your machine's IP address instead of localhost

3. **Start development server**:

   ```bash
   npm start
   ```

4. **Run on device**:
   - Install Expo Go app on your phone
   - Scan the QR code from the terminal
   - Or run `npm run android` / `npm run ios` for simulators

## Environment Variables

- `EXPO_PUBLIC_API_BASE_URL_DEV`: Development API URL (e.g., http://192.168.1.100:8000/api/v1)
- `EXPO_PUBLIC_API_BASE_URL_PROD`: Production API URL
- `NODE_ENV`: Environment (development/production)

## Project Structure

```
mobile/
├── src/
│   ├── components/          # Reusable UI components
│   │   ├── ChatInterface.tsx
│   │   └── EntriesTable.tsx
│   ├── contexts/           # React contexts
│   │   └── AuthContext.tsx
│   ├── navigation/         # Navigation setup
│   │   └── AppNavigator.tsx
│   ├── screens/           # Screen components
│   │   ├── HomeScreen.tsx
│   │   ├── LoginScreen.tsx
│   │   └── RegisterScreen.tsx
│   ├── styles/            # Theme and styling
│   │   └── theme.ts
│   └── config/            # Configuration
│       └── api.ts
├── App.tsx                # Root component
├── app.json              # Expo configuration
└── package.json
```

## Dependencies

- **Expo**: React Native development platform
- **React Navigation**: Navigation library
- **Expo Secure Store**: Secure storage for auth tokens
- **Expo AV**: Audio recording and playback
- **Shared Package**: Common types and services from `../shared/`

## Development Notes

- Uses shared package for API services and types
- Secure storage for authentication tokens
- Voice recording with automatic transcription
- Real-time data synchronization with backend
- Dark theme matching web app design
