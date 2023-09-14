import redis


class RedisQueue(object):
    """Simple Queue with Redis Backend"""

    def __init__(self, name, namespace='queue'):
        """The default connection parameters are: host='localhost', port=6379, db=0"""
        self.__db = redis.Redis(host='localhost', port=6379, db=5, decode_responses=True)
        self.key = '%s:%s' % (namespace, name)

    def qsize(self):
        """Return the approximate size of the queue."""
        return self.__db.llen(self.key)

    def empty(self):
        """Return True if the queue is empty, False otherwise."""
        return self.qsize() == 0

    def put(self, item):
        """Put item into the queue."""
        print('Putting Notification into queue')
        self.__db.rpush(self.key, item)

    def get(self, block=True, timeout=None):
        """Remove and return an item from the queue.

        If optional args block is true and timeout is None (the default), block
        if necessary until an item is available."""
        if block:
            item = self.__db.blpop(self.key, timeout=timeout)
        else:
            if not self.empty():
                item = self.__db.lpop(self.key)
            else:
                return None
        print('Fetched Notification from queue')
        return item

    def get_nowait(self):
        """Equivalent to get(False)."""
        return self.get(False)

    def close_connection(self):
        self.__db.close()


if __name__ == "__main__":
    queue = RedisQueue(name='app-notifications')
    queue.put('Hello;1;2;3;4;5')
    queue.put('Hello;5;4;3;2;1')

    item1 = queue.get_nowait()
    item2 = queue.get_nowait()
    item3 = queue.get_nowait()