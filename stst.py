import bcrypt

password = "11111111"  # replace with the password you want
hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

print(hashed)
