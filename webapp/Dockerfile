FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package.json package-lock.json* npm-shrinkwrap.json* ./

# Install dependencies
RUN npm ci --only=production

# Copy application code
COPY . .

# Build Next.js app
RUN npm run build

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:3000/ || exit 1

# Run the application
CMD ["/bin/sh", "-c", "npm run start -- --port ${PORT:-3000}"]
