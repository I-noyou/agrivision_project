from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def sample(**overrides):
    data = {"state":"Chhattisgarh","district":"Durg","tehsil":"Bori","village":"Temri","khasra":"122/1","soil":"loam","land_acres":0.593,"budget_inr":20000,"water":"medium","season":"kharif","weather":"normal","market":"steady"}
    data.update(overrides)
    return data

def test_health():
    r = client.get('/api/health')
    assert r.status_code == 200 and r.json()['status'] == 'ok'

def test_demo_parcel_lookup():
    r = client.post('/api/parcels/lookup', json=sample())
    assert r.status_code == 200
    assert r.json()['found'] is True
    assert r.json()['parcel']['area_hectares'] == 0.24

def test_unknown_parcel_does_not_fake_lookup():
    r = client.post('/api/parcels/lookup', json=sample(khasra='999'))
    assert r.status_code == 200 and r.json()['found'] is False

def test_optimizer_respects_budget_and_land():
    r = client.post('/api/optimize', json=sample(budget_inr=25000))
    assert r.status_code == 200
    result = r.json()
    assert result['total_cost_inr'] <= 25000
    assert result['allocated_area_acres'] <= result['land_acres']
    assert sum(z['area_acres'] for z in result['zones']) <= result['land_acres'] + .001

def test_invalid_area_rejected():
    r = client.post('/api/optimize', json=sample(land_acres=0))
    assert r.status_code == 422

def test_state_is_chhattisgarh_only():
    r = client.post('/api/optimize', json=sample(state='Maharashtra'))
    assert r.status_code == 422
