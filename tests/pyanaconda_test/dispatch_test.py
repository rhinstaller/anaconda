import mock

class StepTest(mock.TestCase):
    def setUp(self):
        self.setupModules(
            ['logging', 'pyanaconda.anaconda_log', 'block'])

        import pyanaconda
        pyanaconda.anaconda_log = mock.Mock()

    def tearDown(self):
        self.tearDownModules()

    def done_test(self):
        from pyanaconda.dispatch import Step
        from pyanaconda.errors import DispatchError
        s = Step("a_step")
        s.schedule(None)
        s.request(None)
        s.done(None)
        self.assertEquals(s.sched, Step.SCHED_DONE)
        self.assertRaises(DispatchError, s.skip, None)

    def instantiation_test(self):
        from pyanaconda.dispatch import Step
        s = Step("yeah")
        self.assertIsInstance(s, Step)
        # name
        self.assertEqual(s.name, "yeah")
        # default scheduling
        self.assertEqual(s.sched, Step.SCHED_UNSCHEDULED)

    def namesched_test(self):
        from pyanaconda.dispatch import Step
        s = Step("a_step")
        self.assertEqual(s.namesched(Step.SCHED_UNSCHEDULED), "unscheduled")

    def reschedule_test(self):
        from pyanaconda.dispatch import Step
        from pyanaconda.errors import DispatchError
        s = Step("a_step")
        s._reschedule(Step.SCHED_UNSCHEDULED, None)
        self.assertEqual(s.sched, Step.SCHED_UNSCHEDULED)
        s._reschedule(Step.SCHED_SCHEDULED, None)
        self.assertEqual(s.sched, Step.SCHED_SCHEDULED)
        s._reschedule(Step.SCHED_REQUESTED, None)
        self.assertEqual(s.sched, Step.SCHED_REQUESTED)
        self.assertRaises(DispatchError, s._reschedule, Step.SCHED_SKIPPED, None)
        self.assertRaises(DispatchError, s._reschedule, Step.SCHED_UNSCHEDULED, None)
        s._reschedule(Step.SCHED_DONE, None)
        self.assertEqual(s.sched, Step.SCHED_DONE, None)

        s = Step("another_step")
        s._reschedule(Step.SCHED_SKIPPED, None)
        self.assertEqual(s.sched, Step.SCHED_SKIPPED)
        self.assertRaises(DispatchError, s._reschedule, Step.SCHED_SCHEDULED, None)
        self.assertRaises(DispatchError, s._reschedule, Step.SCHED_REQUESTED, None)
        self.assertRaises(DispatchError, s._reschedule, Step.SCHED_DONE, None)

    def request_test(self):
        from pyanaconda.dispatch import Step
        from pyanaconda.errors import DispatchError
        s = Step("a_step")
        s.request(None)
        self.assertRaises(DispatchError, s.skip, None)

    def schedule_test(self):
        from pyanaconda.dispatch import Step
        s = Step("a_step")
        s.schedule(None)
        self.assertEquals(s.sched, Step.SCHED_SCHEDULED)

    def skip_test(self):
        from pyanaconda.dispatch import Step
        from pyanaconda.errors import DispatchError
        s = Step("a_step")
        s.skip(None)
        self.assertEquals(s.sched, Step.SCHED_SKIPPED)
        self.assertRaises(DispatchError, s.done, None)
        self.assertRaises(DispatchError, s.request, None)

    def record_history_test(self):
        from pyanaconda.dispatch import Step
        s = Step("first_step")
        self.assertDictEqual(s.changes, {})

        s2 = Step("second_step")
        s.record_history(s2, Step.SCHED_UNSCHEDULED, Step.SCHED_SCHEDULED)
        self.assertDictEqual(
            s.changes,
            {'second_step' : (Step.SCHED_UNSCHEDULED, Step.SCHED_SCHEDULED)})
        s.record_history(s2, Step.SCHED_SCHEDULED, Step.SCHED_DONE)
        self.assertDictEqual(
            s.changes,
            {'second_step' : (Step.SCHED_UNSCHEDULED, Step.SCHED_DONE)})

    def revert_sched_test(self):
        from pyanaconda.dispatch import Step
        s = Step("first_step")
        s.request(None)
        s.revert_sched(Step.SCHED_UNSCHEDULED, Step.SCHED_REQUESTED)
        self.assertEqual(s.sched, Step.SCHED_UNSCHEDULED)
        s.request(None)
        self.assertRaises(AssertionError, s.revert_sched, Step.SCHED_SKIPPED,
                          Step.SCHED_UNSCHEDULED)

    def tracking_test(self):
        """ Tests that reschedule correctly registers steps to revert """
        from pyanaconda.dispatch import Step
        s1 = Step("first_step")
        s2 = Step("second_step")
        s = Step("current_step")
        s1.schedule(s)
        s2.schedule(s)
        s2.request(s)
        self.assertDictEqual(
            s.changes,
            {"first_step" : (Step.SCHED_UNSCHEDULED, Step.SCHED_SCHEDULED),
             "second_step" : (Step.SCHED_UNSCHEDULED, Step.SCHED_REQUESTED)})

class DispatchTest(mock.TestCase):
    def setUp(self):
        self.setupModules(
            ['logging', 'pyanaconda.anaconda_log', 'block'])

        import pyanaconda
        pyanaconda.anaconda_log = mock.Mock()

    def tearDown(self):
        self.tearDownModules()

    def _getDispatcher(self):
        from pyanaconda.dispatch import Dispatcher
        self.anaconda_obj = mock.Mock()
        return Dispatcher(self.anaconda_obj)

    def done_test(self):
        from pyanaconda.dispatch import Dispatcher
        from pyanaconda.dispatch import Step
        from pyanaconda.errors import DispatchError

        d = self._getDispatcher()
        self.assertFalse(d.step_enabled("betanag"))
        d.schedule_steps("betanag")
        d.done_steps("betanag")
        self.assertTrue(d.step_enabled("betanag"))
        self.assertTrue(d.steps["betanag"], Step.SCHED_DONE)
        self.assertRaises(DispatchError, d.skip_steps, "betanag")

    def instantiation_test(self):
        from pyanaconda.dispatch import Dispatcher
        d = self._getDispatcher()
        self.assertIsInstance(d, Dispatcher)

    def schedule_test(self):
        from pyanaconda.dispatch import Step
        d = self._getDispatcher()
        d.schedule_steps("betanag", "complete")
        self.assertEqual(d.steps["betanag"].sched, Step.SCHED_SCHEDULED)
        self.assertEqual(d.steps["complete"].sched, Step.SCHED_SCHEDULED)
        self.assertEqual(d.steps["bootloader"].sched, Step.SCHED_UNSCHEDULED)
        # impossible to reach nonexistent steps:
        self.assertRaises(KeyError, d.steps.__getitem__, "nonexistent")

    def skip_test(self):
        d = self._getDispatcher()
        d.schedule_steps("betanag", "filtertype", "complete")
        self.assertTrue(d.step_enabled("betanag"))
        d.skip_steps("betanag", "complete")
        self.assertFalse(d.step_enabled("betanag"))
        self.assertFalse(d.step_enabled("complete"))
        self.assertTrue(d.step_enabled("filtertype"))

    def track_scheduling_test(self):
        from pyanaconda.dispatch import Step
        d = self._getDispatcher()
        d.schedule_steps("betanag", "filtertype", "filter")
        d.step = "betanag"
        # tested through the request_steps
        d.request_steps("filtertype", "filter")
        self.assertDictEqual(
            d.steps[d.step].changes,
            {"filtertype" : (Step.SCHED_SCHEDULED, Step.SCHED_REQUESTED),
             "filter" : (Step.SCHED_SCHEDULED, Step.SCHED_REQUESTED)})

    def revert_scheduling_test(self):
        from pyanaconda.dispatch import Step
        d = self._getDispatcher()
        d.schedule_steps("betanag", "filtertype", "filter")
        d.step = "betanag"
        d.request_steps("filtertype", "filter")
        d._revert_scheduling("betanag")
        self.assertEqual(d.steps["filtertype"].sched, Step.SCHED_SCHEDULED)
        self.assertEqual(d.steps["filter"].sched, Step.SCHED_SCHEDULED)
        self.assertDictEqual(d.steps[d.step].changes, {})
