from app import create_app
import os
 
app = create_app()
 
if __name__ == '__main__':
    port = int(os.environ.get('CHAOSUI_PORT', 8090))
    print(f"  Chaos UI starting on http://0.0.0.0:{port}")
    print(f"  Targeting TradeSphere at: {app.config['TARGET_APP_URL']}")
    print(f"  Kubernetes namespace:     {app.config['APP_NAMESPACE']}")
    app.run(host='0.0.0.0', port=port, debug=False,
            threaded=True)   # threaded=True required for SSE streaming