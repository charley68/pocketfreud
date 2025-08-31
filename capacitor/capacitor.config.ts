import { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.pocketfreud.app',
  appName: 'PocketFreud',
  server: {
    url: 'https://pocketfreud.com',   // <- loads your live site
    cleartext: false
  },
  allowNavigation: [
    'pocketfreud.com',
    'www.pocketfreud.com',
    'api.pocketfreud.com'
  ]
};

export default config;

