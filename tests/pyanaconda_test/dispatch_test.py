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
        s.schedule()
        s.request()
        s.done()
        self.assertEquals(s.sched, Step.SCHED_DONE)
        self.assertRaises(DispatchError, s.skip)

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
        s._reschedule(Step.SCHED_UNSCHEDULED)
        self.assertEqual(s.sched, Step.SCHED_UNSCHEDULED)
        s._reschedule(Step.SCHED_SCHEDULED)
        self.assertEqual(s.sched, Step.SCHED_SCHEDULED)
        s._reschedule(Step.SCHED_REQUESTED)
        self.assertEqual(s.sched, Step.SCHED_REQUESTED)
        self.assertRaises(DispatchError, s._reschedule, Step.SCHED_SKIPPED)
        self.assertRaises(DispatchError, s._reschedule, Step.SCHED_UNSCHEDULED)
        s._reschedule(Step.SCHED_DONE)
        self.assertEqual(s.sched, Step.SCHED_DONE)

        s = Step("another_step")
        s._reschedule(Step.SCHED_SKIPPED)
        self.assertEqual(s.sched, Step.SCHED_SKIPPED)
        self.assertRaises(DispatchError, s._reschedule, Step.SCHED_SCHEDULED)
        self.assertRaises(DispatchError, s._reschedule, Step.SCHED_REQUESTED)
        self.assertRaises(DispatchError, s._reschedule, Step.SCHED_DONE)

    def request_test(self):
        from pyanaconda.dispatch import Step
        from pyanaconda.errors import DispatchError
        s = Step("a_step")
        s.request()
        self.assertRaises(DispatchError, s.skip)

    def schedule_test(self):
        from pyanaconda.dispatch import Step
        s = Step("a_step")
        s.schedule()
        self.assertEquals(s.sched, Step.SCHED_SCHEDULED)

    def skip_test(self):
        from pyanaconda.dispatch import Step
        from pyanaconda.errors import DispatchError
        s = Step("a_step")
        s.skip()
        self.assertEquals(s.sched, Step.SCHED_SKIPPED)
        self.assertRaises(DispatchError, s.done)
        self.assertRaises(DispatchError, s.request)

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
