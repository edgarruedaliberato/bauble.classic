#
# test_bauble.py
#
import os
import sys
import unittest
import datetime

from sqlalchemy import *

import bauble
import bauble.db as db
from bauble.types import Enum
from bauble.utils.log import debug
from bauble.view import SearchParser
from bauble.utils.pyparsing import *
from bauble.test import BaubleTestCase
import bauble.meta as meta

"""
Tests for the main bauble module.
"""

class BaubleTests(BaubleTestCase):

    def test_enum_type(self):
        """
        Test bauble.types.Enum
        """
        class Test(db.Base):
            __tablename__ = 'test'
            id = Column(Integer, primary_key=True)
            value = Column(Enum(values=['1', '2', '']), default=u'')
        table = Test.__table__
        table.create(bind=db.engine)
#         t = Test(id=1)
#         self.session.add(t)
#         self.session.commit()
        db.engine.execute(table.insert(), {"id": 1})
        #debug(t.value)



    def test_date_type(self):
        """
        Test bauble.types.Date
        """
        pass

    def test_datetime_type(self):
        """
        Test bauble.types.DateTime
        """
        pass

    def test_base_table(self):
        """
        Test db.Base is setup correctly
        """
        m = meta.BaubleMeta(name=u'name', value=u'value')
        table = m.__table__
        self.session.save(m)
        m = self.session.query(meta.BaubleMeta).first()

        # test that _created and _last_updated were created correctly
        self.assert_(hasattr(m, '_created') \
                     and isinstance(m._created, datetime.datetime))
        self.assert_(hasattr(m, '_last_updated') \
                     and isinstance(m._last_updated, datetime.datetime))


    def test_sequence(self):
        """
        Test that sequences behave like we expect.
        """
        engine = db.engine
        from bauble.meta import BaubleMeta
        table = BaubleMeta.__table__
        #debug(self.session.query(BaubleMeta).all())
        table.insert(values={'id': 100}).execute(bind=engine)
        table.insert(values={'id': 101}).execute(bind=engine)
        # these two lines will fix it but aren't guaranteed to be safe
        maxid = engine.execute('select max(id) from bauble').fetchone()[0]

        # TODO: if it turns out we have to do this then check this recipe:
        # http://www.sqlalchemy.org/trac/wiki/UsageRecipes/SafeCounterColumns
        #if engine.name == 'postgres':
        #    engine.execute("select setval('bauble_id_seq', %s)" % (maxid + 1))

        # if not unique then should raise IntegrityError
        table.insert(values={'name': u'something'}).execute(bind=engine)


        maxid = engine.execute('select max(id) from bauble').fetchone()[0]
        self.assert_(maxid == 102, maxid)


