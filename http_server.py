import http.server
import socketserver
import datetime

# Set the IP and port you want the server to listen on
IP = "0.0.0.0"  # Listen on all available network interfaces
PORT = 8080  # Choose a port number (e.g., 8080)

# Create a custom request handler to handle incoming requests
class MyRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.endswith("getHeartBeat"):
            # If the request ends with "getHeartBeat", send the current system time
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.wfile.write(current_time.encode())
        else:
            # If it's a regular request, serve the file as usual
            super().do_GET()

# Create a socket server that listens on the specified IP and port
with socketserver.TCPServer((IP, PORT), MyRequestHandler) as httpd:
    print(f"Serving on {IP}:{PORT}")

    # Start the server and keep it running
    httpd.serve_forever()