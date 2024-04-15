from os import fork, kill, waitpid
from signal import SIGTERM
from subprocess import run
from sys import exit
from time import sleep

num_processes = 50

children = []

def be_a_child():
    run(["bin/test-crawl"])


for _ in range(num_processes):
    sleep(0.5)
    pid = fork()
    if pid == 0:
        be_a_child()
        exit()
    children.append(pid)

input("Enter to exit...")
for pid in children:
    kill(pid, SIGTERM)

for pid in children:
    waitpid(pid, 0)

print("Done")
