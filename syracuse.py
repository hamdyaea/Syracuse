#!/usr/bin/env python3
# Developer : Hamdy Abou El Anein
# hamdy.aea@protonmail.com

num = int(input("Enter a number : "))

def main(x):
    if x % 2 == 0:
        print(x)
        x = x/2
        x = int(x)
        if x == 1:
            print(x)
            exit(0)
        else:
            main(x)
    else:
        print(x)
        x = (x * 3) + 1
        if x == 1:
            print(x)
            exit(0)
        else:
            main(x)


main(num)
