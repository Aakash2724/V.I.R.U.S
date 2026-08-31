# V.I.R.U.S. — AI Voice Companion

> **V**oice **I**ntelligence & **R**easoning **U**nified **S**ystem  
> Akash's personal AI voice companion, powered by Whisper, Groq, Llama & Edge-TTS.

---

## Getting Started

This project was bootstrapped with [Create React App](https://github.com/facebook/create-react-app).

## Available Scripts

In the project directory, you can run:

### `npm start`

Runs the app in the development mode.  
Open [http://localhost:3000](http://localhost:3000) to view it in your browser.

The page will reload when you make changes.  
You may also see any lint errors in the console.

### `npm test`

Launches the test runner in the interactive watch mode.  
See the section about [running tests](https://facebook.github.io/create-react-app/docs/running-tests) for more information.

### `npm run build`

Builds the app for production to the `build` folder.  
It correctly bundles React in production mode and optimizes the build for the best performance.

The build is minified and the filenames include the hashes.  
Your app is ready to be deployed!

---

## Backend

Start the V.I.R.U.S. backend server with:

```bash
cd backend
uvicorn virus_server:app --reload
```

---

## Tech Stack

- **Frontend**: React, Three.js (plasma blob), WebSockets
- **Backend**: FastAPI, Faster-Whisper, Silero VAD, Groq API, Edge-TTS, Pygame
- **AI**: Llama-3.1-8b-instant via Groq, Whisper-large-v3 (cloud) + small.en (local fallback)
