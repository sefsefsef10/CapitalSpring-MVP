import { initializeApp } from 'firebase/app'
import { getAuth, GoogleAuthProvider } from 'firebase/auth'

// Firebase configuration
const firebaseConfig = {
  apiKey: 'AIzaSyDxq5mMwdsahroOMppQCtd3UoP5hfXYPOI',
  authDomain: 'capitalspring-cdd68.firebaseapp.com',
  projectId: 'capitalspring-cdd68',
  storageBucket: 'capitalspring-cdd68.firebasestorage.app',
  messagingSenderId: '1044744439416',
  appId: '1:1044744439416:web:e2b45ec368b2ddec414f8d',
}

// Initialize Firebase
const app = initializeApp(firebaseConfig)

// Initialize Auth
export const auth = getAuth(app)
export const googleProvider = new GoogleAuthProvider()

// Configure Google provider
googleProvider.setCustomParameters({
  prompt: 'select_account',
})

export default app
