from bootstrap import bootstrap

# The shared postgres package reads POSTGRES_* from os.environ when it is first
# imported, so this runs before any api module imports it.
bootstrap("api")
