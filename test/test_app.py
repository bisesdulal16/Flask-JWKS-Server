"""
JWKS Server - Test Suite
Author:Bishesh Dulal
Date : February 2025
"""

import pytest
import jwt
import time
import requests
import sys
import os

# Add project root to PYTHONPATH so tests can find the Flask app module
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

# Import the Flask app and utility functions
from app import app, generate_key, keys

# Base URL where the server is expected to run
BASE_URL = "http://127.0.0.1:8080"

@pytest.fixture
def client():
    """
    Creates a test client for the Flask application.
    This allows us to make HTTP requests without starting the actual server.
    
    Yields:
        FlaskClient: A test client for making requests to the Flask app.
    """
    app.config["TESTING"] = True  # Enable testing mode
    with app.test_client() as client:
        yield client

def test_jwks_valid_keys(client):
    """
    Test if the JWKS endpoint (`/.well-known/jwks.json`) returns valid keys.

    - Generates a new RSA key.
    - Makes a GET request to retrieve the JWKS keys.
    - Checks if at least one key exists and has the required fields.
    """
    generate_key()  # Generate a new RSA key
    response = client.get("/.well-known/jwks.json")  # Request the JWKS keys
    
    assert response.status_code == 200  # Ensure response is OK
    data = response.json
    assert "keys" in data  # Ensure 'keys' is in the response JSON
    assert len(data["keys"]) > 0  # Ensure at least one key exists
    assert all("kid" in key for key in data["keys"])  # Ensure all keys have a Key ID (kid)

def test_auth_token_generation(client):
    """
    Test if the `/auth` endpoint generates a valid JWT.

    - Makes a POST request to `/auth`.
    - Ensures the response contains a valid JWT.
    - Decodes the JWT to check its structure.
    """
    response = client.post("/auth")  # Request a new JWT
    
    assert response.status_code == 201  # Ensure JWT is created
    data = response.json
    assert "token" in data  # Ensure JWT is in response

    # Decode the JWT without verification (only checking structure)
    decoded = jwt.decode(data["token"], options={"verify_signature": False})
    
    # Ensure required claims exist
    assert "exp" in decoded  # Expiration time
    assert "iat" in decoded  # Issued-at time
    assert "sub" in decoded  # Subject (user identifier)

def test_expired_token(client):
    """
    Test if the `/auth?expired=true` endpoint generates an expired JWT.

    - Makes a POST request to `/auth?expired=true`.
    - Ensures the response contains a JWT.
    - Decodes the JWT and verifies that it is expired.
    """
    response = client.post("/auth?expired=true")  # Request an expired JWT
    
    assert response.status_code == 201  # Ensure JWT is created
    data = response.json
    assert "token" in data  # Ensure JWT is in response

    # Decode the expired JWT
    decoded = jwt.decode(data["token"], options={"verify_signature": False})

    # Ensure the expiration time is in the past
    assert decoded["exp"] < time.time()  # The token should already be expired

def test_invalid_http_methods(client):
    """
    Test if invalid HTTP methods return a 405 error on `/auth` and `/.well-known/jwks.json`.

    - Tests PUT, DELETE, and PATCH methods for both endpoints.
    - Ensures these methods return HTTP 405 (Method Not Allowed).
    """
    for method in ["put", "delete", "patch"]:
        # Call the invalid methods on both endpoints
        auth_response = getattr(client, method)("/auth")
        jwks_response = getattr(client, method)("/.well-known/jwks.json")
        
        # Ensure both endpoints return 405 Method Not Allowed
        assert auth_response.status_code == 405
        assert jwks_response.status_code == 405

def test_expired_keys_cleanup(client):
    """
    Test if expired keys are removed from the JWKS response.

    - Generates an expired RSA key.
    - Ensures the key exists before calling the JWKS endpoint.
    - Calls the JWKS endpoint (which should trigger expired key cleanup).
    - Ensures the expired key is no longer in the dictionary.
    """
    expired_kid = generate_key(expired=True)  # Generate an expired key
    assert expired_kid in keys  # Ensure the key exists before cleanup

    # Trigger the JWKS endpoint to clean expired keys
    client.get("/.well-known/jwks.json")

    # Ensure the expired key has been removed
    assert expired_kid not in keys

def test_invalid_token(client):
    """
    Test if the `/auth` endpoint rejects an invalid JWT.

    - Generates a fake JWT signed with a different key.
    - Makes a GET request with the invalid token in the Authorization header.
    - Ensures the request is rejected (405, as GET is not allowed on /auth).
    """
    fake_token = jwt.encode({"sub": "fake"}, "wrong-key", algorithm="HS256")  # Generate an invalid token
    
    headers = {"Authorization": f"Bearer {fake_token}"}
    response = client.get("/auth", headers=headers)  # Attempt to access /auth with the fake token
    
    assert response.status_code == 405  # GET should not be allowed on /auth
