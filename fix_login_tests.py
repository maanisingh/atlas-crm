import re

# Read the file
with open('orders/tests/test_return_views.py', 'r') as f:
    content = f.read()

# Define replacements
replacements = [
    (r"self\.client\.login\(email='customer@test\.com', password='testpass123'\)", "self.client.force_login(self.customer)"),
    (r"self\.client\.login\(email='customer2@test\.com', password='testpass123'\)", "self.client.force_login(self.customer2)"),
    (r"self\.client\.login\(email='admin@test\.com', password='testpass123'\)", "self.client.force_login(self.admin)"),
    (r"self\.client\.login\(email='manager@test\.com', password='testpass123'\)", "self.client.force_login(self.manager)"),
    (r"self\.client\.login\(email='stockkeeper@test\.com', password='testpass123'\)", "self.client.force_login(self.stock_keeper)"),
    (r"self\.client\.login\(email='finance@test\.com', password='testpass123'\)", "self.client.force_login(self.finance)"),
]

# Apply replacements
for pattern, replacement in replacements:
    content = re.sub(pattern, replacement, content)

# Write back
with open('orders/tests/test_return_views.py', 'w') as f:
    f.write(content)

print("✅ Fixed all login calls")
