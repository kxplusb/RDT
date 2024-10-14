import random

# size = 100000000 #100MB
# size = 200000 #100KB
size = 100000 #100KB
# size = 100 #100KB

if __name__ == "__main__":
    with open('original.txt', 'w', encoding="UTF-8") as f:
        data = ''
        for i in range(size):
            data += chr(random.randint(32, 126))
        # data = 'a'  * size
        f.write(data)
