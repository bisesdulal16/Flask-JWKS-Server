"""
JWKS Server
Author:Bishesh Dulal
Date : February 2025
"""

from flask import Flask, request, jsonify
from datetime import datetime, timedelta, UTC
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import jwt
import uuid
import base64

#Initialize Flask application
app = Flask(__name__)

# Dictionary to store RSA key pairs along with expiration timestamps
keys = {}

def base64url_encode(value: int) -> str:
    """
    Encodes an integer using Base64 URL encoding without padding.
    This is required to format the RSA key components (n and e) for JWKS.
    
    Args:
        value (int): The integer to encode.

    Returns:
        str: Base64 URL encoded string.
    """
    bytes_value = value.to_bytes((value.bit_length() + 7) // 8, 'big')
    return base64.urlsafe_b64encode(bytes_value).rstrip(b'=').decode('utf-8')

def generate_key(expired: bool = False) -> str:
    """
    Generates an RSA key pair and stores it with an expiration timestamp.

    Args:
        expired (bool): If True, generates a key that is already expired.

    Returns:
        str: The unique Key ID (kid) for the generated key.
    """
    # Generate RSA key pair
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    
    # Generate a unique Key ID (KID)
    kid = str(uuid.uuid4())  # Unique Key ID
    
    # Set expiration time (1 hour from now by default)
    expiry = datetime.now(UTC) + timedelta(hours=1)

    # If expired flag is True, set expiration time in the past (expired key)
    if expired:
        expiry = datetime.now(UTC) - timedelta(minutes=5)

    # Store the keys in the dictionary
    keys[kid] = {
        'private_key': private_key,
        'public_key': private_key.public_key(),
        'expiry': expiry
    }
    return kid

@app.route('/.well-known/jwks.json', methods=['GET'])
def jwks_endpoint():
    """
    Returns the JSON Web Key Set (JWKS) containing valid public keys.
    
    - Filters out expired keys.
    - Encodes public key components in Base64 URL format.

    Returns:
        JSON response containing active public keys.
    """
    now = datetime.now(UTC)

    # Remove expired keys from the dictionary
    expired_keys = [kid for kid, key in keys.items() if key['expiry'] < now]
    for kid in expired_keys:
        del keys[kid]

    # Prepare the JWKS response with valid keys
    valid_keys = [
        {
            "kty": "RSA",
            "use": "sig",
            "kid": kid,
            "n": base64url_encode(key['public_key'].public_numbers().n),
            "e": base64url_encode(key['public_key'].public_numbers().e),
            "alg": "RS256"
        }
        for kid, key in keys.items()
    ]
    
    # Return JWKS with proper content type
    return jsonify(keys=valid_keys), 200, {'Content-Type': 'application/json'}

@app.route('/auth', methods=['POST'])
def auth_endpoint():
    """
    Generates a JWT signed with an RSA private key.

    - If 'expired=true' is passed as a query parameter, returns an expired JWT.
    - Otherwise, generates a fresh JWT.

    Returns:
        JSON response containing the JWT.
    """
    expired = 'expired' in request.args

    # Find an existing expired key if requested, otherwise generate a new one
    kid = next((k for k, v in keys.items() if v['expiry'] < datetime.now(UTC)), None) if expired else None

    if not kid:
        kid = generate_key(expired=expired)

    # Serialize private key in PEM format
    private_pem = keys[kid]['private_key'].private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    # Set expiration time for JWT
    exp_time = datetime.now(UTC) + timedelta(minutes=5)
    if expired:
        exp_time = datetime.now(UTC) - timedelta(minutes=5)

    # JWT Payload
    payload = {
        'sub': 'example_user',
        'iat': datetime.now(UTC),
        'exp': exp_time
    }

    # Generate JWT with RS256 algorithm
    try:
        token = jwt.encode(
            payload,
            private_pem,
            algorithm='RS256',
            headers={'kid': kid}
        )
    except Exception as e:
        return jsonify(error=f"JWT encoding error: {str(e)}"), 500

    return jsonify(token=token), 201

@app.route('/.well-known/jwks.json', methods=['PUT', 'POST', 'DELETE', 'PATCH'])
def jwks_invalid_methods():
    """
    Handles invalid HTTP methods for the JWKS endpoint.

    Returns:
        JSON error response with status code 405.
    """
    return jsonify(error="Method Not Allowed"), 405

@app.route('/auth', methods=['GET', 'PUT', 'DELETE', 'PATCH', 'HEAD'])
def auth_invalid_methods():
    """
    Handles invalid HTTP methods for the /auth endpoint.

    Returns:
        JSON error response with status code 405.
    """
    return jsonify(error="Method Not Allowed"), 405


if __name__ == '__main__':
    """
    Starts the Flask application on port 8080.
    
    - Runs on all available network interfaces (0.0.0.0).
    - Debug mode is disabled for security.
    """
    app.run(host='0.0.0.0', port=8080, debug=False)
