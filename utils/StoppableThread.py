import ctypes
import threading
import time


class StoppableThread(threading.Thread):
    def __init__(self, group=None, target=None, name=None,
                 args=(), kwargs=None, *, daemon=None):
        threading.Thread.__init__(self, group, target, name, args, kwargs, daemon=daemon)
        # self.setDaemon(True) # TODO here! avoiding $h!t wait.

    def get_id(self):
        # returns id of the respective thread
        if hasattr(self, '_thread_id'):
            return self._thread_id
        for id, thread in threading._active.items():
            if thread is self:
                return id

    def stop(self):
        thread_id = self.get_id()
        # print(f'Kill id :{thread_id}')
        # 精髓就是这句话，给线程发过去一个exceptions，线程就那边响应完就停了
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id,
                                                         ctypes.py_object(SystemExit))
        if res > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0)
            print('Exception raise failure')


# def blocker():
#     print("start block")
#     time.sleep(10)
#     print('NONONONONONONO!')
#
#
# t1 = StoppableThread( target=blocker)
# t1.start()
# time.sleep(3)
# t1.stop()
# t1.join()
# print("end")

# t1 = StoppableThread('Thread 1')
# t2 = StoppableThread('Thread 2')
# t1.start()
# t2.start()
# time.sleep(5)
# t1.raise_exception()
# t2.raise_exception()
# t1.join()
# t2.join()
# print("Finished")
