import datetime
from itertools import cycle
import sched
import time

import nidaqmx as ni


WHITE_PORT = 'Dev1/port0/line7'
RED_PORT = 'Dev1/port0/line6'

NUM_DAYS = 15
MORNING_HOUR = 9
NIGHT_HOUR = 21


def make_task():
    task = ni.Task()
    task.do_channels.add_do_chan(WHITE_PORT)
    task.do_channels.add_do_chan(RED_PORT)
    return task


def cleanup(task):
    task.stop()
    task.close()


def begin_day(task):
    task.write([True, False])


def begin_night(task):
    task.write([False, True])


def print_schedule(schedule):
    """ Prints the light schedule for the operator
    """
    for time, fn in schedule:
        strings = ('Will activate daytime lighting', 'Will activate nighttime lighting')
        if fn == begin_day:
            message = strings[0]
        else:
            message = strings[1]
        time_str = time.strftime('%c')
        print(f'{time_str}: {message}')


def run():
    scheduler = sched.scheduler(time.time, time.sleep)
    # One event for 9AM, one event for 9PM
    total_events = NUM_DAYS * 2
    task = make_task()

    start_time = datetime.datetime.now()
    # Find the next time the lights should change, this will be the starting point of the calculations
    # to determine the rest of the critical times
    this_morning = start_time.replace(hour=MORNING_HOUR, minute=0, second=0, microsecond=0)
    this_night = start_time.replace(hour=NIGHT_HOUR, minute=0, second=0, microsecond=0)
    day_night_cycle = cycle([begin_day, begin_night])
    if start_time < this_morning:
        # The script was started prior to 9AM on day 1
        print('Activating nighttime lighting immediately')
        begin_night(task)
        first_sched_time = this_morning
    elif start_time < this_night:
        # Script was started between 9AM and 9PM on day 1
        print('Activating daytime lighting immediately')
        begin_day(task)
        # Shift the day-night cycle so the first scheduled event
        # runs begin_night
        next(day_night_cycle)
        first_sched_time = this_night
    else:
        # The script was started after 9PM on day 1 (0?)
        # Same as starting the script before 9AM
        print('Activating nighttime lighting immediately')
        begin_night(task)
        # Calculate the time of the next morning
        first_sched_time = this_morning + datetime.timedelta(days=1)
    task.start()
    # Compute a bunch of times spaced 12hrs apart, starting with first_sched_time
    first_sched_time = datetime.datetime.now()
    sched_times = [first_sched_time + datetime.timedelta(seconds=10*n) for n in range(total_events)]
    # The scheduler object expects a float similar to that returned by time.time
    # This transforms the datetime objects to match that expectation
    sched_times_seconds = [dt.timestamp() for dt in sched_times]
    # Associate a function (begin_day or night) with each time
    # Collapse the cycle iterable to a list to avoid weird bugs related
    # to iterating over it and shifting the index
    sched_events = list(zip(sched_times_seconds, day_night_cycle))
    # Make a copy of sched_events for printing
    debug_events = [(evt_time, sched_events[n][1]) for n, evt_time in enumerate(sched_times)]
    print_schedule(debug_events)


    for evt_time, evt_fn in sched_events:
        scheduler.enterabs(evt_time, 1, evt_fn, argument=(task,))
    print('Starting...')
    try:
        scheduler.run(blocking=True)
    except Exception as e:
        # The script may have been cancelled early
        print(e)
        print('Cleaning up reserved GPIO ports')
        cleanup(task)
        return
    print('Done')
    cleanup(task)


if __name__ == '__main__':
    run()

