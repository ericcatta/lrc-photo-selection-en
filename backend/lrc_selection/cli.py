import argparse
import os
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description='LrC Photo Selection — English edition, local only')
    parser.add_argument('--data-dir', type=Path, default=Path.home() / 'Library/Application Support/LrC Photo Selection EN')
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--show-connection', action='store_true', help='Show the local token for plugin setup; this is not an API key')
    args = parser.parse_args()
    os.umask(0o077)
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
    from .app import create_app, load_connection_token
    if args.show_connection:
        print('Local connection token (do not share):')
        print(load_connection_token(args.data_dir))
        return
    app = create_app(args.data_dir)
    import uvicorn
    print(f'Open http://127.0.0.1:{args.port} — no catalog is opened automatically.')
    uvicorn.run(app, host='127.0.0.1', port=args.port, access_log=False)

if __name__ == '__main__':
    main()
