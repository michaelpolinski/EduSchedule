import random
file='local_settings.py'
key=''.join(random.SystemRandom().choice('abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)') for i in range(50))
with open(file) as f:
    t=f.read().replace('PUT_SECRET_KEY_HERE',key)
with open(file, "w") as f:
    f.write(t)
exit()