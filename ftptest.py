import ftplib
import io

# Connection details - use the same as in your interface
host = "10.88.0.64"  # Replace with your actual host
port = 21
username = "username"  # Replace with your actual username
password = "password"  # Replace with your actual password

# Create a simple test file
test_data = "This is a test file for FTP upload."

try:
    # Connect to the FTP server
    print(f"Connecting to {host}:{port}...")
    ftp = ftplib.FTP()
    ftp.timeout = 30
    ftp.connect(host, port)
    print("Connection established, logging in...")
    ftp.login(username, password)
    print("Login successful")

    # Enable passive mode
    print("Setting passive mode...")
    ftp.set_pasv(True)

    # Upload a test file
    print("Uploading test file...")
    ftp.storbinary('STOR test_file.txt', io.BytesIO(test_data.encode('utf-8')))
    print("File uploaded successfully!")

    # Close the connection
    ftp.quit()
    print("FTP connection closed")

except Exception as e:
    print(f"Error: {str(e)}")