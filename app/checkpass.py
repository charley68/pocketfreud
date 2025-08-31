from werkzeug.security import generate_password_hash, check_password_hash

# Step 1: Store a hashed password (e.g., from a user signup)
password = "bob"
hashed_password = generate_password_hash(password)

print("Stored hash:", hashed_password)

# Step 2: Later, check the user’s input against the hash
user_input = input("Enter your password: ")

if check_password_hash(hashed_password, user_input):
    print("✅ Password is correct!")
else:
    print("❌ Invalid password!")

