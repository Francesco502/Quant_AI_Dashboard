# Quant AI Dashboard - Frontend

This is the new Next.js frontend for the Quant AI Dashboard, designed with the Apple Human Interface Guidelines.

## Getting Started

1.  **Install Dependencies**
    ```bash
    cd web
    npm install
    ```

2.  **Run Development Server**
    ```bash
    npm run dev
    ```

3.  **Open in Browser**
    Visit [http://localhost:8686](http://localhost:8686)

## Architecture

*   **Framework**: Next.js 14 (App Router)
*   **Styling**: Tailwind CSS v4 + Shadcn UI
*   **State Management**: React Hooks + API Client
*   **Backend Connection**: Connects to FastAPI at `http://localhost:8000`

## Project Structure

*   `src/app`: Pages and Layouts
*   `src/components/ui`: Reusable UI components (Buttons, Cards, etc.)
*   `src/components/layout`: Global layout components (Sidebar, Header)
*   `src/lib/api.ts`: API Client for backend integration

## Features

*   **Apple Design System**: Glassmorphism, San Francisco-style typography, smooth animations.
*   **Real-time Data**: Fetches market data from the existing Python backend.
*   **Interactive Charts**: High-performance charts using Recharts.
