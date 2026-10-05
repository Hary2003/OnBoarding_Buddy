# syntax=docker/dockerfile:1
# ==============================================================================
# Production Dockerfile for OnBoarding Buddy Frontend
# High-performance, lightweight Nginx static file server & API reverse proxy
# ==============================================================================

FROM nginx:1.27-alpine

LABEL maintainer="OnBoarding Buddy Team"
LABEL description="Production Nginx container serving OnBoarding Buddy frontend with API reverse proxy"

# Clean up default Nginx boilerplate configuration and html files
RUN rm -rf /etc/nginx/conf.d/default.conf /usr/share/nginx/html/*

# Copy custom Nginx reverse proxy configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy frontend static assets (HTML, CSS, JS)
COPY index.html /usr/share/nginx/html/index.html
COPY style.css /usr/share/nginx/html/style.css
COPY app.js /usr/share/nginx/html/app.js

# Create static alias symlink so /static/* directly resolves
RUN ln -sf /usr/share/nginx/html /usr/share/nginx/html/static

# Ensure proper read permissions for web server
RUN chmod -R 755 /usr/share/nginx/html

# Expose standard HTTP web port
EXPOSE 80

# Container liveness & readiness healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://127.0.0.1:80/healthz || exit 1

# Launch Nginx in foreground mode
CMD ["nginx", "-g", "daemon off;"]
