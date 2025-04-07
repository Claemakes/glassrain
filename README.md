# GlassRain - Render Deployment Package

## Application Overview

GlassRain is a premium home improvement platform with the following key features:

### Home Dashboard
- High-fidelity 3D model of the property with rotate and zoom capabilities
- Contextual suggestions appear when zooming in on different areas
- "Go Inside" button to access the blueprint view in the Elevate tab
- Quick action cards for easy navigation to main features

### Elevate Tab
- **Blueprint View**: Shows scanned rooms with gold outlines and rooms pending scans
- **Scan Room**: Interface for scanning and mapping rooms
- **Saved Designs**: Library of saved room designs
- Room customization with furniture and decor from 22+ stores

### Services Tab
- Categories of home services with AI-powered pricing
- Service tiers (Basic, Standard, Premium)
- Contractor matching based on service needs

## Required Environment Variables

- DATABASE_URL: Your PostgreSQL connection string
- MAPBOX_API_KEY: Your Mapbox API key
- FLASK_SECRET_KEY: A secure random string

## After Deployment

Once deployed, your GlassRain application will be available at your Render service URL.
