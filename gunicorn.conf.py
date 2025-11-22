import multiprocessing
import os

# temporary
def get_all_sub(folder_path):
    files = []

    for dir_or_file in os.listdir(folder_path):
        dir_or_file = os.path.join(folder_path, dir_or_file)
        if os.path.isfile(dir_or_file):
            files.append(dir_or_file)
            continue

        files.extend(get_all_sub(dir_or_file))

    return files


reload = True
reload_extra_files = get_all_sub(os.path.join('cashier_app', 'static'))


# maybe (+ require changes)
# accesslog = '-'
# errorlog = '-'

access_log_format = '%(h)s %(l)s %(u)s %(t)s \u001b[1;38;2;26;176;240m"%(r)s"\u001b[0m %(s)s %(b)s "%(f)s" "%(a)s"'
# h remote address
# l '-'
# u user name (if HTTP Basic auth used)
# t date of the request
# r status line (e.g. GET / HTTP/1.1)
# m request method
# U URL path without query string
# q query string
# H protocol
# s status
# B response length
# b response length or '-' (CLF format)
# f referrer (note: header is referer)
# a user agent
# T request time in seconds
# M request time in milliseconds
# D request time in microseconds
# L request time in decimal seconds
# p process ID
# {header}i request header
# {header}o response header
# {variable}e environment variable

# prob permanent (some require changes)
wsgi_app = 'cashier_app:create_app()'

# bind = "127.0.0.1:8000" unix:PATH
workers = min(12, multiprocessing.cpu_count() * 2 + 1)

# ssl config stuff (will be handled by ngingx?)

# the header forwarding stuff
