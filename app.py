from flask import Flask, render_template, jsonify
import json
from collections import Counter
from pathlib import Path
import plotly.express as px
import pandas as pd

app = Flask(__name__)

def load_data():
    """Load and process SSH attempt data"""
    try:
        with open('ssh_attempts.json', 'r') as f:
            attempts = json.load(f)
        
        # Count IPs and cities
        ip_counts = Counter(item['ip'] for item in attempts)
        city_counts = Counter(item['city'] for item in attempts)
        
        # Prepare top 10 lists
        top_ips = [{'ip': ip, 'count': count} 
                  for ip, count in ip_counts.most_common(10)]
        top_cities = [{'city': city, 'count': count} 
                     for city, count in city_counts.most_common(10)]
        
        # Prepare map data
        map_data = pd.DataFrame([
            {'city': city, 'count': count}
            for city, count in city_counts.items()
        ])
        
        return {
            'top_ips': top_ips,
            'top_cities': top_cities,
            'map_data': map_data,
            'max_count': max(city_counts.values()) if city_counts else 0
        }
    except Exception as e:
        print(f"Error loading data: {e}")
        return {'top_ips': [], 'top_cities': [], 'map_data': pd.DataFrame(), 'max_count': 0}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/data')
def get_data():
    data = load_data()
    
    # Create choropleth map
    if not data['map_data'].empty:
        fig = px.choropleth(
            data['map_data'],
            locations='city',
            locationmode='city',
            color='count',
            range_color=[0, data['max_count']],
            color_continuous_scale='Purples_r',
            title='SSH Attempt Origins',
            template='plotly_dark'
        )
        
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=0, r=0, t=30, b=0),
            height=500
        )
        
        map_html = fig.to_html(full_html=False)
    else:
        map_html = "<p>No data available</p>"
    
    return jsonify({
        'map_html': map_html,
        'top_ips': data['top_ips'],
        'top_cities': data['top_cities']
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)