from app import app
from invoicepro.database.database import db
from invoicepro.database.models import User, CompanySettings

with app.app_context():
    # create a user if not exists
    user = User.query.first()
    if not user:
        user = User(name="Test", email="test@test.com")
        user.set_password("password")
        db.session.add(user)
        db.session.commit()
        cs = CompanySettings(user_id=user.id)
        db.session.add(cs)
        db.session.commit()

client = app.test_client()
client.post("/auth/login", data={"email": "test@test.com", "password": "password"}, follow_redirects=True)
response = client.get("/dashboard/", follow_redirects=True)
print("Status:", response.status_code)
if response.status_code != 200:
    print(response.get_data(as_text=True))
