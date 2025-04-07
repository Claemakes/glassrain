"""
GlassRain API Server - Complete Solution
This is a fully contained Flask application for GlassRain.
No background processes are needed - just run this file directly.
"""
from flask import Flask, jsonify, request, send_from_directory, make_response
import os
import psycopg2
import psycopg2.extras
import json
import logging
import uuid
import requests
from decimal import Decimal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("glassrain.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# JSON encoder that can handle Decimal objects
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super(DecimalEncoder, self).default(o)

# Set JSON encoder for Flask
app.json_encoder = DecimalEncoder

# Get database connection
def get_db_connection():
    """Get a connection to the PostgreSQL database"""
    try:
        db_url = os.environ.get('DATABASE_URL')
        if db_url:
            conn = psycopg2.connect(db_url)
            logger.info("Connected to database using DATABASE_URL")
            return conn
        else:
            conn = psycopg2.connect(
                dbname=os.environ.get('PGDATABASE', 'postgres'),
                user=os.environ.get('PGUSER', 'postgres'),
                password=os.environ.get('PGPASSWORD', 'postgres'),
                host=os.environ.get('PGHOST', 'localhost'),
                port=os.environ.get('PGPORT', '5432')
            )
            logger.info("Connected to database using individual parameters")
            return conn
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        raise

# Add CORS and iframe headers
@app.after_request
def add_headers(response):
    """Add headers to allow iframe embedding and CORS"""
    response.headers['X-Frame-Options'] = 'ALLOWALL'
    response.headers['Content-Security-Policy'] = "frame-ancestors *"
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

# Simple index page
@app.route('/')
def index():
    """Simple HTML status page for GlassRain"""
    return """
    <html>
        <head>
            <title>GlassRain API Server</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
                h1 { color: #3B82F6; }
                .endpoint { margin-bottom: 10px; }
                .method { display: inline-block; width: 60px; font-weight: bold; }
                a { color: #3B82F6; text-decoration: none; }
                a:hover { text-decoration: underline; }
                .status { padding: 10px; background-color: #E5E7EB; border-radius: 5px; margin: 20px 0; }
                .status.ok { background-color: #D1FAE5; }
                .status.error { background-color: #FEE2E2; }
            </style>
        </head>
        <body>
            <h1>GlassRain API Server</h1>
            <div class="status ok">Server is running!</div>
            
            <h2>API Endpoints</h2>
            <div class="endpoint"><span class="method">GET</span> <a href="/api/status">/api/status</a> - Server status</div>
            <div class="endpoint"><span class="method">GET</span> <a href="/api/service-categories">/api/service-categories</a> - Get service categories</div>
            <div class="endpoint"><span class="method">GET</span> <a href="/api/services">/api/services</a> - Get all services</div>
            <div class="endpoint"><span class="method">GET</span> <a href="/api/mapbox-token">/api/mapbox-token</a> - Get Mapbox token</div>
            <div class="endpoint"><span class="method">GET</span> <a href="/api/service-tiers">/api/service-tiers</a> - Get service tier levels</div>

            <h2>Pages</h2>
            <div class="endpoint"><span class="method">GET</span> <a href="/dashboard">/dashboard</a> - Dashboard</div>
            <div class="endpoint"><span class="method">GET</span> <a href="/address-entry">/address-entry</a> - Address Entry</div>
        </body>
    </html>
    """

# Status endpoint
@app.route('/api/status')
def status():
    """Returns server status"""
    # Check database connection
    db_status = "connected"
    db_error = None
    
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            cursor.close()
            conn.close()
        else:
            db_status = "error"
            db_error = "Could not connect to database"
    except Exception as e:
        db_status = "error"
        db_error = str(e)
    
    return jsonify({
        "status": "ok",
        "service": "GlassRain API",
        "version": "1.0.0",
        "database": {
            "status": db_status,
            "error": db_error
        },
        "mapbox_api": {
            "status": "available" if os.environ.get("MAPBOX_API_KEY") else "unavailable"
        }
    })

# Service categories endpoint
@app.route('/api/service-categories')
def get_service_categories():
    """Return list of service categories"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cursor.execute("""
            SELECT id, name, description, icon
            FROM service_categories
            ORDER BY name
        """)
        categories = cursor.fetchall()
        
        # For each category, get its services
        for category in categories:
            cursor.execute("""
                SELECT s.id, s.name, s.description, COUNT(cs.contractor_id) as provider_count
                FROM services s
                LEFT JOIN contractor_services cs ON s.id = cs.service_id
                WHERE s.category_id = %s
                GROUP BY s.id
                ORDER BY s.name
            """, (category['id'],))
            services = cursor.fetchall()
            category['services'] = services
        
        cursor.close()
        conn.close()
        
        return jsonify(categories)
    except Exception as e:
        logger.error(f"Error in get_service_categories: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Services endpoint with proper categories
@app.route('/api/services')
def get_services():
    """Return list of available services with categories and subcategories"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get category from query params if provided
        category_id = request.args.get('category_id')
        
        if category_id:
            # If category is provided, return all services in that category
            cursor.execute("""
                SELECT s.*, sc.name as category_name, COUNT(cs.contractor_id) as provider_count
                FROM services s
                JOIN service_categories sc ON s.category_id = sc.id
                LEFT JOIN contractor_services cs ON s.id = cs.service_id
                WHERE s.category_id = %s
                GROUP BY s.id, sc.name
                ORDER BY s.name
            """, (category_id,))
            services = cursor.fetchall()
            
            # Get service tiers for each service
            for service in services:
                cursor.execute("""
                    SELECT id, name, multiplier
                    FROM service_tiers
                    ORDER BY multiplier
                """)
                tiers = cursor.fetchall()
                service['tiers'] = tiers
            
            cursor.close()
            conn.close()
            
            return jsonify(services)
        else:
            # Return all categories with their services
            cursor.execute("""
                SELECT 
                    sc.id, 
                    sc.name, 
                    sc.description, 
                    sc.icon,
                    COUNT(DISTINCT s.id) as service_count
                FROM service_categories sc
                LEFT JOIN services s ON sc.id = s.category_id
                GROUP BY sc.id
                ORDER BY sc.name
            """)
            categories = cursor.fetchall()
            
            # For each category, get its services
            for category in categories:
                cursor.execute("""
                    SELECT s.id, s.name, s.description, COUNT(cs.contractor_id) as provider_count
                    FROM services s
                    LEFT JOIN contractor_services cs ON s.id = cs.service_id
                    WHERE s.category_id = %s
                    GROUP BY s.id
                    ORDER BY s.name
                """, (category["id"],))
                services = cursor.fetchall()
                category['services'] = services
            
            cursor.close()
            conn.close()
            
            return jsonify(categories)
    except Exception as e:
        logger.error(f"Error in get_services: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Mapbox token endpoint
@app.route('/api/mapbox-token')
def mapbox_token():
    """Return Mapbox API token"""
    mapbox_key = os.environ.get("MAPBOX_API_KEY", "")
    return jsonify({"token": mapbox_key})

# Service tiers endpoint
@app.route('/api/service-tiers')
def get_service_tiers():
    """Return service tiers with their multipliers"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cursor.execute("""
            SELECT id, name, description, multiplier
            FROM service_tiers
            ORDER BY multiplier
        """)
        tiers = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify(tiers)
    except Exception as e:
        logger.error(f"Error in get_service_tiers: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Static files
@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files"""
    return send_from_directory('static', filename)

# Address Entry page
@app.route('/address-entry')
def address_entry():
    """Render the address entry page"""
    return """
    <html>
        <head>
            <title>GlassRain Address Entry</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 0; padding: 0; }
                .container { width: 100%; max-width: 1200px; margin: 0 auto; padding: 20px; }
                h1 { color: #3B82F6; }
                .form-group { margin-bottom: 20px; }
                label { display: block; margin-bottom: 5px; font-weight: bold; }
                input[type="text"] { width: 100%; padding: 8px; font-size: 16px; border: 1px solid #ccc; border-radius: 4px; }
                button { background-color: #3B82F6; color: white; border: none; padding: 10px 20px; font-size: 16px; cursor: pointer; border-radius: 4px; }
                button:hover { background-color: #2563EB; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>GlassRain Address Entry</h1>
                <form id="addressForm">
                    <div class="form-group">
                        <label for="address">Address</label>
                        <input type="text" id="address" name="address" placeholder="Enter your address" required>
                    </div>
                    <button type="submit">Continue</button>
                </form>
            </div>
            <script>
                document.getElementById('addressForm').addEventListener('submit', async (e) => {
                    e.preventDefault();
                    const address = document.getElementById('address').value;
                    
                    try {
                        const response = await fetch('/api/process-address', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({ address }),
                        });
                        
                        const data = await response.json();
                        
                        if (data.success) {
                            window.location.href = '/dashboard?address_id=' + data.address_id;
                        } else {
                            alert('Error: ' + data.error);
                        }
                    } catch (error) {
                        alert('Error processing address: ' + error.message);
                    }
                });
            </script>
        </body>
    </html>
    """

# Dashboard page
@app.route('/dashboard')
def dashboard():
    """Render the main dashboard page"""
    return """
    <html>
        <head>
            <title>GlassRain Dashboard</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 0; padding: 0; }
                .container { width: 100%; max-width: 1200px; margin: 0 auto; padding: 20px; }
                h1 { color: #3B82F6; }
                .card { border: 1px solid #ccc; border-radius: 4px; padding: 20px; margin-bottom: 20px; }
                .card-title { font-size: 18px; font-weight: bold; margin-bottom: 10px; }
                .button { background-color: #3B82F6; color: white; border: none; padding: 10px 20px; font-size: 16px; cursor: pointer; border-radius: 4px; text-decoration: none; display: inline-block; }
                .button:hover { background-color: #2563EB; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>GlassRain Dashboard</h1>
                <div class="card">
                    <div class="card-title">Services</div>
                    <p>Find and schedule home improvement services.</p>
                    <a href="/services" class="button">Explore Services</a>
                </div>
                
                <div class="card">
                    <div class="card-title">Elevate</div>
                    <p>Design your space with virtual furniture.</p>
                    <a href="/elevate" class="button">Start Designing</a>
                </div>
                
                <div class="card">
                    <div class="card-title">DIY Projects</div>
                    <p>Get help with your DIY home improvement projects.</p>
                    <a href="/diy" class="button">View DIY Projects</a>
                </div>
            </div>
        </body>
    </html>
    """

# Process address data
@app.route('/api/process-address', methods=['POST'])
def process_address():
    """Process address data from the form, geocode using Mapbox, and save to database"""
    try:
        data = request.json
        address = data.get('address')
        email = data.get('email', '')  # Optional email
        
        if not address:
            return jsonify({"success": False, "error": "Address is required"}), 400
        
        # Get Mapbox token
        mapbox_key = os.environ.get("MAPBOX_API_KEY", "")
        if not mapbox_key:
            logger.error("Mapbox API key not found")
            return jsonify({"success": False, "error": "Mapbox API key not configured"}), 500
        
        # Geocode the address using Mapbox
        try:
            geocode_url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{address}.json?access_token={mapbox_key}"
            geocode_response = requests.get(geocode_url)
            
            if geocode_response.status_code != 200:
                logger.error(f"Mapbox API error: {geocode_response.text}")
                return jsonify({"success": False, "error": "Error geocoding address"}), 500
                
            location_data = geocode_response.json()
            
            if not location_data.get("features") or len(location_data["features"]) == 0:
                return jsonify({"success": False, "error": "Address not found"}), 400
                
            feature = location_data["features"][0]
            location = feature["geometry"]["coordinates"]
            formatted_address = feature["place_name"]
            
            # Generate a unique ID for this address
            address_id = str(uuid.uuid4())
            
            # Save to database if connected
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                
                # Check if we need to create the homes table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS homes (
                        id VARCHAR(36) PRIMARY KEY,
                        address TEXT NOT NULL,
                        formatted_address TEXT,
                        longitude FLOAT,
                        latitude FLOAT,
                        email TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Insert the new home
                cursor.execute("""
                    INSERT INTO homes (id, address, formatted_address, longitude, latitude, email)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (address_id, address, formatted_address, location[0], location[1], email))
                
                conn.commit()
                cursor.close()
                conn.close()
                
                logger.info(f"Saved home with ID: {address_id}")
            except Exception as db_error:
                logger.error(f"Database error while saving home: {str(db_error)}")
                # Still continue, just log the error
                
            # Prepare response data
            home_data = {
                "id": address_id,
                "address": address,
                "formatted_address": formatted_address,
                "longitude": location[0],
                "latitude": location[1],
                "email": email
            }
            
            return jsonify({
                "success": True, 
                "address_id": address_id,
                "address": formatted_address,
                "home_data": home_data
            })
                
        except Exception as geocode_error:
            logger.error(f"Error geocoding address: {str(geocode_error)}")
            return jsonify({"success": False, "error": f"Error geocoding address: {str(geocode_error)}"}), 500
            
    except Exception as e:
        logger.error(f"Error in process_address: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    try:
        port = int(os.environ.get('PORT', 5000))
        logger.info(f"Starting GlassRain API server on port {port}")
        app.run(host='0.0.0.0', port=port)
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        raise