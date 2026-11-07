"""Expose the Flask application and start its local development server."""

from app import create_app


app = create_app()


if __name__ == "__main__":
    app.run()
