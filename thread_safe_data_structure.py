import threading


class WindowSlots:
    def __init__(self, capacity) -> None:
        self.capacity = capacity
        self.data = [None] * self.capacity
        self.front = 0
        self.rear = 0
        self.lock = threading.Lock()
        self.event = threading.Event()

    def push(self, item):
        self.lock.acquire()
        if (self.rear + 1) % self.capacity == self.front:
            self.front = (self.front + 1) % self.capacity
        rear = self.rear
        front = self.front
        self.rear = (self.rear + 1) % self.capacity
        self.lock.release()

        self.data[rear] = item

        if front != rear:
            self.event.set()

    def top(self):
        while True:
            self.lock.acquire()
            if self.front == self.rear:
                self.lock.release()
                self.event.wait()
            else:
                item = self.data[self.front]
                self.lock.release()
                if isinstance(item, tuple):
                    return item[1]
                return item

    def top_unblock(self):
        self.lock.acquire()
        if self.front == self.rear:
            self.lock.release()
            return None
        else:
            item = self.data[self.front]
            self.lock.release()
            return item

    # def transform(self, func):
    #     while True:
    #         self.lock.acquire()
    #         if self.front == self.rear:
    #             self.lock.release()
    #             self.event.wait()
    #         else:
    #             self.data[self.front]
    #             self.lock.release()
    #             return item