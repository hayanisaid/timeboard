from __future__ import division
from .exceptions import OutOfBoundsError
from .core import get_period
from numpy import searchsorted


class Workshift(object):
    """A constituent of timeline. 
    
    Timeboard's timeline is a sequence of workshifts. Each workshift has
    a label which defines whether this workshift is on-duty or off-duty 
    under a certain schedule. 
    A workshift can span one or more consecutive base units. 
    
    Parameters
    ----------
    timeboard : Timeboard
    location : int (>=0)
        Position of the workshift on the timeline of the timeboard (zero-based).
    schedule: _Schedule
        
    Raises
    ------
    OutOfBoundsError (LookupError)
        If `location` points outside the timeboard or is negative.
        
    Attributes
    ----------
    start_time : Timestamp
        When the workshift starts.
    end_time : Timestamp
        When the workshift ends.
    duration : int (>0)
        Number of base unit making up the workshift.
    label
        An application-specific label associated with the workshift. 
        Schedule's `selector` interprets the label to identify the duty
        of the workshift under this schedule.
    is_on_duty : bool
        True if the workship is on-duty under given `schedule`.
    is_off_duty : bool
        True if the workship is off-duty under given `schedule`.
    
    Notes
    -----
    Calling  Timeboard's instance or its `get_workshift` method provides a
    convenient way to instantiate a workshift from a point in time instead of 
    calling Workshift() constructor directly. 
    """

    def __init__(self, timeboard, location, schedule=None):
        if schedule is None:
            schedule = timeboard.default_schedule
        try:
            self._label = schedule.label(location)
        except TypeError:
            raise TypeError('Workshift location = `{!r}`: expected '
                            'integer-like '
                            'received {}'.format(location, type(location)))
        except IndexError:
            raise OutOfBoundsError("Workshift location {} "
                                   "is outside timeboard {}".
                                   format(location, timeboard.compact_str))
        # negative locations are not allowed? why?
        # if location <0:
        #     raise OutOfBoundsError("Received location={}. Negative location is "
        #                            "not allowed.".format(location))
        self._tb = timeboard
        self._loc = location
        self._schedule = schedule

    @property
    def start_time(self):
        # TODO: Refactor. _Timeline methods should not be called from this class
        return self._tb._timeline.get_ws_start_time(self._loc)

    @property
    def end_time(self):
        # TODO: Refactor. _Timeline methods should not be called from this class
        return self._tb._timeline.get_ws_end_time(self._loc)

    @property
    def duration(self):
        # TODO: Refactor. _Timeline methods should not be called from this class
        return self._tb._timeline.get_ws_duration(self._loc)

    def to_timestamp(self):
        """The characteristic time used to represent the workshift. 
        
        The rule to calculate the timestamp is defined by `workshift_ref` 
        parameter of the timeboard.
        
        Returns
        -------
        Timestamp
        """
        # TODO: Refactor. _Timeline methods should not be called from this class
        return self._tb._timeline.get_ws_ref_time(self._loc)

    def __repr__(self):
        return "Workshift(tb, {!r})\ntb={!r}".format(self._loc, self._tb)

    @property
    def compact_str(self):
        duration_str = ''
        if self.duration != 1:
            duration_str = str(self.duration) + 'x'
        return "{}'{}' at {}".\
                format(duration_str,
                       self._tb.base_unit_freq,
                       get_period(self.to_timestamp(),
                                  freq=self._tb.base_unit_freq))

    def __str__(self):
        return "Workshift " + self.compact_str + \
               "\n\n{}".format(self._tb.to_dataframe(self._loc, self._loc))

    @property
    def label(self):
        return self._label

    @property
    def is_on_duty(self):
        return self._schedule.is_on_duty(self._loc)

    @property
    def is_off_duty(self):
        return self._schedule.is_off_duty(self._loc)

    @property
    def is_void(self):
        return False

    def rollforward(self, steps=0, duty='on'):
        """
        Return a workshift which is `steps` workshifts away in the future. 
        
        `duty` parameter selects which workshifts are counted as steps.
        
        Parameters
        ----------
        steps: int, optional (default 0)
        duty: {'on', 'off', 'same', 'alt', 'any'} , optional (default 'on')
            'on' - step on on-duty workshifts only
            'off' - step on off-duty workshifts only
            'same' - step only on workshifts with the same duty status as self
            'alt' - step only on workshifts with the duty status other than 
            that of self
            'any' - step on all workshifts
    
        Returns
        -------
        Workshift
        
        Raises
        ------
        OutOfBoundsError (LookupError)
            If the method attempted to roll outside the timeboard.

        Notes
        -----
        The method is executed in two stages. The first stage finds the 
        workshift at step 0. The second stage fulfils the required number of 
        steps (if any) starting from the zero step workshift.
        
        If self has the same duty as specified by `duty` parameter, then 
        the zero step workshift is self, otherwise it is the first workshift 
        toward the future which conforms to `duty` parameter. If `steps`=0,
        the method terminates here and returns the zero step workshift.
         
        If `steps` is positive, the methods counts workshifts toward the future
        stepping only on workshifts with the specified duty, and returns the 
        last workshift on which it stepped. For example, with `steps`=1 the 
        method returns the workshift following the zero step workshift, 
        subject to duty.
        
        If `steps` is negative, the method works in the same way but moving
        toward the past from the zero step workshift. For example, with 
        `steps`=-1 the method returns the workshift preceding the zero step 
        workshift, subject to duty.
        
        See also
        --------
        + (__add__) :  `ws + n` is the same as ws.rollforward(n, duty='on')
        rollback : return a workshift from the past
            `rollback` differs from `rollforward` only in the definition of 
            the zero step workshift and the default direction of stepping.
        """
        schedule = self._schedule
        idx = schedule.on_duty_index
        if (duty == 'off') or (duty == 'same' and self.is_off_duty) or (
                        duty == 'alt' and self.is_on_duty):
            idx = schedule.off_duty_index
        elif duty == 'any':
            idx = schedule.index

        len_idx = len(idx)
        i = searchsorted(idx, self._loc)
        if i == len_idx or i + steps < 0 or i + steps >= len_idx:
            return self._tb._handle_out_of_bounds("Rollforward of ws {} with "
                       "steps={}, duty={}, schedule={}"
                       ".".format(self.to_timestamp(), steps, duty,
                                  schedule.activity))

        return Workshift(self._tb, idx[i + steps], schedule)

    def rollback(self, steps=0, duty='on'):
        """
        Return a workshift which is `steps` workshifts away in the past. 
        
        `duty` parameter selects which workshifts are counted as steps.

        Parameters
        ----------
        steps: int, optional (default 0)
        duty: {'on', 'off', 'same', 'alt', 'any'} , optional (default 'on')
            'on' - step on on-duty workshifts only
            'off' - step on off-duty workshifts only
            'same' - step only on workshifts with the same duty status as self
            'alt' - step only on workshifts with the duty status other than 
            that of self
            'any' - step on all workshifts
    
        Returns
        -------
        Workshift
        
        Raises
        ------
        OutOfBoundsError (LookupError)
            If the method attempted to roll outside the timeboard.

        Notes
        -----
        The method is executed in two stages. The first stage finds the 
        workshift at step 0. The second stage fulfils the required number of 
        steps (if any) starting from the zero step workshift.
        
        If self has the same duty as specified by `duty` parameter, then 
        the zero step workshift is self, otherwise it is the first workshift 
        toward the past which conforms to `duty` parameter. If `steps`=0,
        the method terminates here and returns the zero step workshift.
         
        If `steps` is positive, the methods counts workshifts toward the past
        stepping only on workshifts with the specified duty, and returns the 
        last workshift on which it stepped. For example, with `steps`=1 the 
        method returns the workshift preceding the zero step workshift, 
        subject to duty.
        
        If `steps` is negative, the method works in the same way but moving
        toward the future from the zero step workshift. For example, with 
        `steps`=-1 the method returns the workshift following the zero step 
        workshift, subject to duty.
        
        See also
        --------
        - (__sub__) :  `ws - n` is the same as ws.rollback(n, duty='on')
        rollforward : return a workshift from the future
            `rollforward` differs from `rollback` only in the definition of 
            the zero step workshift and the default direction of stepping.
        """
        # TODO: Optimize rollback and rolloforward to compy with DRY?
        schedule = self._schedule
        idx = schedule.on_duty_index
        if (duty == 'off') or (duty == 'same' and self.is_off_duty) or (
                        duty == 'alt' and self.is_on_duty):
            idx = schedule.off_duty_index
        elif duty == 'any':
            idx = schedule.index

        # TODO: Optimize this search
        len_idx = len(idx)
        i = len_idx - 1
        while i >= 0 and idx[i] > self._loc:
            i -= 1

        if i == -1 or i - steps < 0 or i - steps >= len_idx:
            return self._tb._handle_out_of_bounds("Rollback of ws {} with "
                       "steps={}, duty={}, schedule={}"
                       ".".format(self.to_timestamp(), steps, duty,
                                  schedule.activity))

        return Workshift(self._tb, idx[i - steps], schedule)

    def __add__(self, other):
        """ws + n is the same as ws.rollforward(n, duty='on')"""
        if isinstance(other, int):
            return self.rollforward(steps=other, duty='on')
        else:
            return NotImplemented

    def __sub__(self, other):
        """ws - n is the same as ws.rollback(n, duty='on')"""
        if isinstance(other, int):
            return self.rollback(steps=other, duty='on')
        elif isinstance(other, type(self)):
            return NotImplemented
        else:
            return NotImplemented
