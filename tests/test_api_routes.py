from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_route_exists():
    response = client.get('/api/health')
    assert response.status_code == 200


def test_auth_login_route_exists():
    response = client.post('/api/auth/login', json={'login': 'demo', 'password': 'demo'})
    assert response.status_code in (200, 401, 403)


def test_users_collection_route_exists():
    response = client.get('/api/users')
    assert response.status_code in (200, 401)


def test_scenarios_route_exists():
    response = client.get('/api/scenarios')
    assert response.status_code == 200
