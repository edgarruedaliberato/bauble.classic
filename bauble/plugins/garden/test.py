# -*- coding: utf-8 -*-
#
# Copyright 2008-2010 Brett Adams
# Copyright 2015 Mario Frasca <mario@anche.no>.
#
# This file is part of bauble.classic.
#
# bauble.classic is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# bauble.classic is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with bauble.classic. If not, see <http://www.gnu.org/licenses/>.

import os
import datetime
import unittest

import gtk

import logging
logger = logging.getLogger(__name__)

from nose import SkipTest
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import object_session

#import bauble
import bauble.db as db
from bauble.test import BaubleTestCase, update_gui, check_dupids
import bauble.utils as utils
from bauble.plugins.garden.accession import Accession, AccessionEditor, \
    AccessionNote, Voucher, SourcePresenter, Verification, dms_to_decimal, \
    latitude_to_dms, longitude_to_dms
from bauble.plugins.garden.source import Source, Collection, SourceDetail, \
    SourceDetailEditor, CollectionPresenter
from bauble.plugins.garden.plant import Plant, PlantNote, \
    PlantChange, PlantEditor, is_code_unique, branch_callback
from bauble.plugins.garden.location import Location, LocationEditor
from bauble.plugins.garden.propagation import Propagation, PropRooted, \
    PropCutting, PropSeed, PropagationEditor
from bauble.plugins.plants.geography import Geography
from bauble.plugins.plants.family import Family
from bauble.plugins.plants.genus import Genus
from bauble.plugins.plants.species_model import Species
import bauble.plugins.plants.test as plants_test
from bauble.plugins.garden.institution import Institution, InstitutionEditor
import bauble.prefs as prefs


accession_test_data = ({'id': 1, 'code': u'2001.1', 'species_id': 1},
                       {'id': 2, 'code': u'2001.2', 'species_id': 2,
                        'source_type': u'Collection'},
                       )

plant_test_data = ({'id': 1, 'code': u'1', 'accession_id': 1,
                    'location_id': 1, 'quantity': 1},
                   {'id': 2, 'code': u'1', 'accession_id': 2,
                    'location_id': 1, 'quantity': 1},
                   {'id': 3, 'code': u'2', 'accession_id': 2,
                    'location_id': 1, 'quantity': 1},
                   )

location_test_data = ({'id': 1, 'name': u'Somewhere Over The Rainbow',
                       'code': u'RBW'},
                      )

geography_test_data = [{'id': 1, 'name': u'Somewhere'}]

collection_test_data = ({'id': 1, 'accession_id': 2, 'locale': u'Somewhere',
                         'geography_id': 1},
                        )

default_propagation_values = \
    {'notes': u'test notes',
     'date': datetime.date(2011, 11, 25)}

default_cutting_values = \
    {'cutting_type': u'Nodal',
     'length': 2,
     'length_unit': u'mm',
     'tip': u'Intact',
     'leaves': u'Intact',
     'leaves_reduced_pct': 25,
     'flower_buds': u'None',
     'wound': u'Single',
     'fungicide': u'Physan',
     'media': u'standard mix',
     'container': u'4" pot',
     'hormone': u'Auxin powder',
     'cover': u'Poly cover',
     'location': u'Mist frame',
     'bottom_heat_temp': 65,
     'bottom_heat_unit': u'F',
     'rooted_pct': 90}

default_seed_values = {
    'pretreatment': u'Soaked in peroxide solution',
    'nseeds': 24,
    'date_sown': datetime.date.today(),  # utils.today_str(),
    'container': u"tray",
    'media': u'standard seed compost',
    'location': u'mist tent',
    'moved_from': u'mist tent',
    'moved_to': u'hardening table',
    'media': u'standard mix',
    'germ_date': datetime.date.today(),  # utils.today_str(),
    'germ_pct': 99,
    'nseedlings': 23,
    'date_planted': datetime.date.today(),
    }

test_data_table_control = ((Accession, accession_test_data),
                           (Location, location_test_data),
                           (Plant, plant_test_data),
                           (Geography, geography_test_data),
                           (Collection, collection_test_data))


def setUp_data():
    """
    create_test_data()
    # if this method is called again before tearDown_test_data is called you
    # will get an error about the test data rows already existing in the
    # database
    """
    for cls, data in test_data_table_control:
        table = cls.__table__
        for row in data:
            table.insert().execute(row).close()
        for col in table.c:
            utils.reset_sequence(col)
    i = Institution()
    i.name = u'TestInstitution'
    i.technical_contact = u'TestTechnicalContact Name'
    i.email = u'contact@test.com'
    i.contact = u'TestContact Name'
    i.code = u'TestCode'


# TODO: if we ever get a GUI tester then do the following
# test all possible combinations of entering data into the accession editor
# 1. new accession without source
# 2. new accession with source
# 3. existing accession without source
# 4. existing accession with new source
# 5. existing accession with existing source
# - create test for parsing latitude/longitude entered into the lat/lon entries


def test_duplicate_ids():
    """
    Test for duplicate ids for all .glade files in the gardens plugin.
    """
    import bauble.plugins.garden as mod
    import glob
    head, tail = os.path.split(mod.__file__)
    files = glob.glob(os.path.join(head, '*.glade'))
    for f in files:
        assert(not check_dupids(f))


class GardenTestCase(BaubleTestCase):

    def __init__(self, *args):
        super(GardenTestCase, self).__init__(*args)

    def setUp(self):
        super(GardenTestCase, self).setUp()
        plants_test.setUp_data()
        self.family = Family(family=u'Cactaceae')
        self.genus = Genus(family=self.family, genus=u'Echinocactus')
        self.species = Species(genus=self.genus, sp=u'grusonii')
        self.sp2 = Species(genus=self.genus, sp=u'texelensis')
        self.session.add_all([self.family, self.genus, self.species, self.sp2])
        self.session.commit()

    def tearDown(self):
        super(GardenTestCase, self).tearDown()
        if hasattr(self, 'editor') and self.editor is not None:
            editor_name = self.editor.__class__.__name__
            presenter_name = self.editor.presenter.__class__.__name__
            view_name = self.editor.presenter.view.__class__.__name__
            self.editor.presenter.cleanup()
            del self.editor
            assert utils.gc_objects_by_type(editor_name) == [], \
                '%s not deleted' % editor_name
            assert utils.gc_objects_by_type(presenter_name) == [], \
                '%s not deleted' % presenter_name
            assert utils.gc_objects_by_type(view_name) == [], \
                '%s not deleted' % view_name

    def create(self, class_, **kwargs):
        obj = class_(**kwargs)
        self.session.add(obj)
        return obj


class ContactTests(GardenTestCase):

    def __init__(self, *args):
        super(ContactTests, self).__init__(*args)

    # def test_delete(self):
    #     acc = self.create(Accession, species=self.species, code=u'1')
    #     contact = Contact(name=u'name')
    #     donation = Donation()
    #     donation.contact = contact
    #     acc.source = donation
    #     self.session.commit()
    #     self.session.close()
    #     # test that we can't delete a contact if it has corresponding
    #     # donations
    #     import bauble
    #     session = db.Session()
    #     contact = session.query(Contact).filter_by(name=u'name').one()

    #     shouldn't be allowed to delete contact if it has donations, what
    #     is happening here is that when deleting the contact the
    #     corresponding donations.contact_id's are being be set to null
    #     which isn't allowed by the scheme....is this the best we can do?
    #     or can we get some sort of error when creating a dangling
    #     reference

    #     session.delete(contact)
    #     self.assertRaises(DBAPIError, session.commit)

    #def itest_contact_editor(self):
    #    """
    #    Interactively test the ContactEditor
    #    """
    #    raise SkipTest('separate view from presenter, then test presenter')
    #    loc = self.create(Contact, name=u'some contact')
    #    editor = ContactEditor(model=loc)
    #    editor.start()
    #    del editor
    #    assert utils.gc_objects_by_type('ContactEditor') == [], \
    #        'ContactEditor not deleted'
    #    assert utils.gc_objects_by_type('ContactEditorPresenter') == [], \
    #        'ContactEditorPresenter not deleted'
    #    assert utils.gc_objects_by_type('ContactEditorView') == [], \
    #        'ContactEditorView not deleted'


class PlantTests(GardenTestCase):

    def __init__(self, *args):
        super(PlantTests, self).__init__(*args)

    def setUp(self):
        super(PlantTests, self).setUp()
        self.accession = self.create(Accession,
                                     species=self.species, code=u'1')
        self.location = self.create(Location, name=u'site', code=u'STE')
        self.plant = self.create(Plant, accession=self.accession,
                                 location=self.location, code=u'1', quantity=1)
        self.session.commit()

    def tearDown(self):
        super(PlantTests, self).tearDown()

    def test_constraints(self):
        """
        Test the contraints on the plant table.
        """
        # test that we can't have duplicate codes with the same accession
        plant2 = Plant(accession=self.accession, location=self.location,
                       code=self.plant.code, quantity=1)
        self.session.add(plant2)
        self.assertRaises(IntegrityError, self.session.commit)
        # rollback the IntegrityError so tearDown() can do its job
        self.session.rollback()

    def test_delete(self):
        """
        Test that when a plant is deleted...
        """
        raise SkipTest('Not Implemented')

    def test_editor_addnote(self):
        raise SkipTest('Not Implemented')

    def test_duplicate(self):
        """
        Test Plant.duplicate()
        """
        p = Plant(accession=self.accession, location=self.location, code=u'2',
                  quantity=52)
        self.session.add(p)
        note = PlantNote(note=u'some note')
        note.plant = p
        note.date = datetime.date.today()
        change = PlantChange(from_location=self.location,
                             to_location=self.location, quantity=1)
        change.plant = p
        self.session.commit()
        dup = p.duplicate(code=u'3')
        assert dup.notes is not []
        assert dup.changes is not []
        self.session.commit()

    def test_bulk_plant_editor(self):
        """
        Test creating multiple plants with the plant editor.
        """
        import gtk

        # use our own plant because PlantEditor.commit_changes() will
        # only work in bulk mode when the plant is in session.new
        p = Plant(accession=self.accession, location=self.location, code=u'2',
                  quantity=52)
        self.editor = PlantEditor(model=p)
        #editor.start()
        update_gui()
        rng = '2,3,4-6'

        for code in utils.range_builder(rng):
            q = self.session.query(Plant).join('accession').\
                filter(and_(Accession.id == self.plant.accession.id,
                            Plant.code == utils.utf8(code)))
            self.assert_(not q.first(), 'code already exists')

        widgets = self.editor.presenter.view.widgets
        # make sure the entry gets a Problem added to it if an
        # existing plant code is used in bulk mode
        widgets.plant_code_entry.set_text('1,' + rng)
        widgets.plant_quantity_entry.set_text(u'2')
        update_gui()
        problem = (self.editor.presenter.PROBLEM_DUPLICATE_PLANT_CODE,
                   self.editor.presenter.view.widgets.plant_code_entry)
        self.assert_(problem in self.editor.presenter.problems,
                     'no problem added for duplicate plant code')

        # create multiple plant codes
        widgets.plant_code_entry.set_text(rng)
        update_gui()
        self.editor.handle_response(gtk.RESPONSE_OK)

        for code in utils.range_builder(rng):
            q = self.session.query(Plant).join('accession').\
                filter(and_(Accession.id == self.plant.accession.id,
                            Plant.code == utils.utf8(code)))
            self.assert_(q.first(), 'plant %s.%s not created' %
                         (self.accession, code))

    def test_editor(self):
        """
        Interactively test the PlantEditor
        """
        raise SkipTest('separate view from presenter, then test presenter')
        for plant in self.session.query(Plant):
            self.session.delete(plant)
        for location in self.session.query(Location):
            self.session.delete(location)
        self.session.commit()

        #editor = PlantEditor(model=self.plant)
        loc = Location(name=u'site1', code=u'1')
        loc2 = Location(name=u'site2', code=u'2')
        loc2a = Location(name=u'site2a', code=u'2a')
        self.session.add_all([loc, loc2, loc2a])
        self.session.commit()
        p = Plant(accession=self.accession, location=loc, quantity=1)
        editor = PlantEditor(model=p)
        editor.start()

    def test_branch_editor(self):
        import gtk

        # test argument checks
        #
        # TODO: these argument checks make future tests fail because
        # the PlantEditor is never cleaned up
        #
        # self.assert_(PlantEditor())
        # self.assertRaises(CheckConditionError, PlantEditor, branch_mode=True)

        # plant = Plant(accession=self.accession, location=self.location,
        #               code=u'33', quantity=5)
        # self.assertRaises(CheckConditionError, PlantEditor, model=plant,
        #                   branch_mode=True)
        #self.accession.plants.remove(plant) # remove from session
        # TODO: test check where quantity < 2

        quantity = 5
        self.plant.quantity = quantity
        self.session.commit()
        self.editor = PlantEditor(model=self.plant, branch_mode=True)
        update_gui()

        widgets = self.editor.presenter.view.widgets
        new_quantity = 2
        widgets.plant_quantity_entry.props.text = new_quantity
        update_gui()
        self.editor.handle_response(gtk.RESPONSE_OK)

        # there should only be three plants,
        new_plant = self.session.query(Plant).\
            filter(Plant.code != self.plant.code).first()
        # test the quantity was set properly on the new plant
        assert new_plant.quantity == new_quantity, new_plant.quantity
        self.session.refresh(self.plant)
        # test the quantity is updated on the original plant
        assert self.plant.quantity == quantity - new_plant.quantity, \
            "%s == %s - %s" % (self.plant.quantity, quantity,
                               new_plant.quantity)
        # test the quantity for the change is the same as the quantity
        # for the plant
        assert new_plant.changes[0].quantity == new_plant.quantity, \
            "%s == %s" % (new_plant.changes[0].quantity, new_plant.quantity)
        # test the parent_plant for the change is the same as the
        # original plant
        assert new_plant.changes[0].parent_plant == self.plant, \
            'change.parent_plant != original plant'

    def test_branch_callback(self):
        """
        Test bauble.plugins.garden.plant.branch_callback()
        """
        raise SkipTest('Not Implemented')
        for plant in self.session.query(Plant):
            self.session.delete(plant)
        for location in self.session.query(Location):
            self.session.delete(location)
        self.session.commit()

        #editor = PlantEditor(model=self.plant)
        loc = Location(name=u'site1', code=u'1')
        loc2 = Location(name=u'site2', code=u'2')
        quantity = 5
        plant = Plant(accession=self.accession, code=u'1', location=loc,
                      quantity=quantity)
        self.session.add_all([loc, loc2, plant])
        self.session.commit()

        branch_callback([plant])
        new_plant = self.session.query(Plant).filter(
            Plant.code != u'1').first()
        self.session.refresh(plant)
        assert plant.quantity == quantity - new_plant.quantity, \
            "%s == %s - %s" % (plant.quantity, quantity, new_plant.quantity)
        assert new_plant.changes[0].quantity == new_plant.quantity, \
            "%s == %s" % (new_plant.changes[0].quantity, new_plant.quantity)

    def test_is_code_unique(self):
        """
        Test bauble.plugins.garden.plant.is_code_unique()
        """
        self.assertFalse(is_code_unique(self.plant, u'1'))
        self.assert_(is_code_unique(self.plant, '01'))
        self.assertFalse(is_code_unique(self.plant, '1-2'))
        self.assertFalse(is_code_unique(self.plant, '01-2'))


class PropagationTests(GardenTestCase):

    def __init__(self, *args):
        super(PropagationTests, self).__init__(*args)

    def setUp(self):
        super(PropagationTests, self).setUp()
        self.accession = self.create(
            Accession, species=self.species, code=u'1')
        # self.location = self.create(Location, name=u'name', code=u'code')
        # self.plant = self.create(Plant, accession=self.accession,
        #                          location=self.location, code=u'2')
        self.session.commit()

    def tearDown(self):
        #self.session.delete(self.location)
        #self.session.delete(self.plant)
        #self.session.commit()
        #self.session.begin()
        super(PropagationTests, self).tearDown()

    def test_accession_prop(self):
        # 'Accession' object has no attribute 'propagations'
        """
        Test the Accession->AccessionPropagation->Propagation relation
        """
        raise SkipTest('Not Implemented')
        loc = Location(name=u'name', code=u'code')
        plant = Plant(accession=self.accession, location=loc, code=u'1',
                      quantity=1)
        prop = Propagation()
        prop.plant = plant
        prop.prop_type = u'UnrootedCutting'
        cutting = PropCutting(**default_cutting_values)
        cutting.propagation = prop
        self.session.commit()
        self.assert_(prop in self.accession.propagations)
        self.assert_(prop.accession == self.accession)

    def test_plant_prop(self):
        """
        Test the Plant->PlantPropagation->Propagation relation
        """
        prop = Propagation()
        loc = self.create(Location, name=u'site1', code=u'1')
        plant = self.create(Plant, accession=self.accession, location=loc,
                            code=u'1', quantity=1)
        prop.prop_type = u'UnrootedCutting'
        cutting = PropCutting(**default_cutting_values)
        cutting.propagation = prop
        plant.propagations.append(prop)
        self.session.commit()
        self.assert_(prop in plant.propagations)
        self.assert_(prop.plant == plant)

    def test_get_summary(self):
        loc = Location(name=u'name', code=u'code')
        plant = Plant(accession=self.accession, location=loc, code=u'1',
                      quantity=1)
        prop = Propagation()
        prop.plant = plant
        prop.prop_type = u'UnrootedCutting'
        cutting = PropCutting(**default_cutting_values)
        cutting.propagation = prop
        rooted = PropRooted()
        rooted.cutting = cutting
        self.session.commit()
        summary = prop.get_summary()
        #debug(summary)
        self.assert_(summary)

        prop = Propagation()
        prop.prop_type = u'Seed'
        prop.plant = plant
        seed = PropSeed(**default_seed_values)
        seed.propagation = prop
        self.session.commit()
        summary = prop.get_summary()
        #debug(summary)
        self.assert_(summary)

    def test_cutting_property(self):
        loc = Location(name=u'name', code=u'code')
        plant = Plant(accession=self.accession, location=loc, code=u'1',
                      quantity=1)
        prop = Propagation()
        prop.plant = plant
        prop.prop_type = u'UnrootedCutting'
        prop.accession = self.accession
        cutting = PropCutting(**default_cutting_values)
        cutting.propagation = prop
        rooted = PropRooted()
        rooted.cutting = cutting
        self.session.add(rooted)
        self.session.commit()

        self.assert_(rooted in prop._cutting.rooted)

        rooted_id = rooted.id
        cutting_id = cutting.id
        self.assert_(rooted_id, 'no prop_rooted.id')

        # setting the _cutting property on Propagation should cause
        # the cutting and its rooted children to be deleted
        prop._cutting = None
        self.session.commit()
        self.assert_(not self.session.query(PropCutting).get(cutting_id))
        self.assert_(not self.session.query(PropRooted).get(rooted_id))

    def test_seed_property(self):
        loc = Location(name=u'name', code=u'code')
        plant = Plant(accession=self.accession, location=loc, code=u'1',
                      quantity=1)
        prop = Propagation()
        plant.propagations.append(prop)
        prop.prop_type = u'Seed'
        prop.accession = self.accession
        seed = PropSeed(**default_seed_values)
        self.session.add(seed)
        seed.propagation = prop
        self.session.commit()

        self.assert_(seed == prop._seed)
        seed_id = seed.id

        # this should cause the cutting and its rooted children to be deleted
        prop._seed = None
        self.session.commit()
        self.assert_(not self.session.query(PropSeed).get(seed_id))

    def test_cutting_editor(self):
        loc = Location(name=u'name', code=u'code')
        plant = Plant(accession=self.accession, location=loc, code=u'1',
                      quantity=1)
        propagation = Propagation()
        plant.propagations.append(propagation)
        self.editor = PropagationEditor(model=propagation)
        widgets = self.editor.presenter.view.widgets
        self.assertTrue(widgets is not None)
        view = self.editor.presenter.view
        view.widget_set_value('prop_type_combo', u'UnrootedCutting')
        view.widget_set_value('prop_date_entry', utils.today_str())
        cutting_presenter = self.editor.presenter._cutting_presenter
        for widget, attr in cutting_presenter.widget_to_field_map.iteritems():
            #debug('%s=%s' % (widget, default_cutting_values[attr]))
            view.widget_set_value(widget, default_cutting_values[attr])
        update_gui()
        self.editor.handle_response(gtk.RESPONSE_OK)
        self.editor.commit_changes()
        model = self.editor.model
        s = object_session(model)
        s.expire(model)
        self.assert_(model.prop_type == u'UnrootedCutting')
        for attr, value in default_cutting_values.iteritems():
            v = getattr(model._cutting, attr)
            self.assert_(v == value, '%s = %s(%s)' % (attr, value, v))
        self.editor.session.close()

    def test_seed_editor_commit(self):
        loc = Location(name=u'name', code=u'code')
        plant = Plant(accession=self.accession, location=loc, code=u'1',
                      quantity=1)
        propagation = Propagation()
        plant.propagations.append(propagation)
        editor = PropagationEditor(model=propagation)
        widgets = editor.presenter.view.widgets
        seed_presenter = editor.presenter._seed_presenter
        view = editor.presenter.view

        # set default values in editor widgets
        view.widget_set_value('prop_type_combo', u'Seed')
        view.widget_set_value('prop_date_entry',
                              default_propagation_values['date'])
        view.widget_set_value('notes_textview',
                              default_propagation_values['notes'])
        for widget, attr in seed_presenter.widget_to_field_map.iteritems():
            w = widgets[widget]
            if isinstance(w, gtk.ComboBoxEntry) and not w.get_model():
                widgets[widget].child.props.text = default_seed_values[attr]
            view.widget_set_value(widget, default_seed_values[attr])

        # update the editor, send the RESPONSE_OK signal and commit the changes
        update_gui()
        editor.handle_response(gtk.RESPONSE_OK)
        editor.presenter.cleanup()
        model_id = editor.model.id
        editor.commit_changes()
        editor.session.close()

        s = db.Session()
        propagation = s.query(Propagation).get(model_id)

        self.assert_(propagation.prop_type == u'Seed')
        # make sure the each value in default_seed_values matches the model
        for attr, expected in default_seed_values.iteritems():
            v = getattr(propagation._seed, attr)
            if isinstance(v, datetime.date):
                format = prefs.prefs[prefs.date_format_pref]
                v = v.strftime(format)
                if isinstance(expected, datetime.date):
                    expected = expected.strftime(format)
            self.assert_(v == expected, '%s = %s(%s)' % (attr, expected, v))

        for attr, expected in default_propagation_values.iteritems():
            v = getattr(propagation, attr)
            self.assert_(v == expected, '%s = %s(%s)' % (attr, expected, v))

        s.close()

    def test_seed_editor_load(self):
        loc = Location(name=u'name', code=u'code')
        plant = Plant(accession=self.accession, location=loc, code=u'1',
                      quantity=1)
        propagation = Propagation(**default_propagation_values)
        propagation.prop_type = u'Seed'
        propagation._seed = PropSeed(**default_seed_values)
        plant.propagations.append(propagation)

        editor = PropagationEditor(model=propagation)
        widgets = editor.presenter.view.widgets
        seed_presenter = editor.presenter._seed_presenter
        view = editor.presenter.view
        self.assertTrue(view is not None)

        update_gui()

        # check that the values loaded correctly from the model in the
        # editor widget
        def get_widget_text(w):
            if isinstance(w, gtk.TextView):
                return w.get_buffer().props.text
            elif isinstance(w, gtk.Entry):
                return w.props.text
            elif isinstance(w, gtk.ComboBoxEntry):
                return w.get_active_text()
            else:
                raise ValueError('%s not supported' % type(w))

        # make sure the default values match the values in the widgets
        date_format = prefs.prefs[prefs.date_format_pref]
        for widget, attr in editor.presenter.widget_to_field_map.iteritems():
            if not attr in default_propagation_values:
                continue
            default = default_propagation_values[attr]
            if isinstance(default, datetime.date):
                default = default.strftime(date_format)
            value = get_widget_text(widgets[widget])
            self.assert_(value == default,
                         '%s = %s (%s)' % (attr, value, default))

        # check the default for the PropSeed and SeedPresenter
        for widget, attr in seed_presenter.widget_to_field_map.iteritems():
            if not attr in default_seed_values:
                continue
            default = default_seed_values[attr]
            if isinstance(default, datetime.date):
                default = default.strftime(date_format)
            if isinstance(default, int):
                default = str(default)
            value = get_widget_text(widgets[widget])
            self.assert_(value == default,
                         '%s = %s (%s)' % (attr, value, default))

    def test_editor(self):
        """
        Interactively test the PropagationEditor
        """
        raise SkipTest('separate view from presenter, then test presenter')
        from bauble.plugins.garden.propagation import PropagationEditor
        propagation = Propagation()
        #propagation.prop_type = u'UnrootedCutting'
        propagation.accession = self.accession
        editor = PropagationEditor(model=propagation)
        propagation = editor.start()
        logger.debug(propagation)
        self.assert_(propagation.accession)


class VoucherTests(GardenTestCase):

    def __init__(self, *args):
        super(VoucherTests, self).__init__(*args)

    def setUp(self):
        super(VoucherTests, self).setUp()
        self.accession = self.create(
            Accession, species=self.species, code=u'1')
        self.session.commit()

    def tearDown(self):
        super(VoucherTests, self).tearDown()

    def test_voucher(self):
        """
        Test the Accession.voucher property
        """
        voucher = Voucher(herbarium=u'ABC', code=u'1234567')
        voucher.accession = self.accession
        self.session.commit()
        voucher_id = voucher.id
        self.accession.vouchers.remove(voucher)
        self.session.commit()
        self.assert_(not self.session.query(Voucher).get(voucher_id))

        # test that if we set voucher.accession to None then the
        # voucher is deleted but not the accession
        voucher = Voucher(herbarium=u'ABC', code=u'1234567')
        voucher.accession = self.accession
        self.session.commit()
        voucher_id = voucher.id
        acc_id = voucher.accession.id
        voucher.accession = None
        self.session.commit()
        self.assert_(not self.session.query(Voucher).get(voucher_id))
        self.assert_(self.session.query(Accession).get(acc_id))


class SourceTests(GardenTestCase):

    def __init__(self, *args):
        super(SourceTests, self).__init__(*args)

    def setUp(self):
        super(SourceTests, self).setUp()
        self.accession = self.create(
            Accession, species=self.species, code=u'1')

    def tearDown(self):
        super(SourceTests, self).tearDown()

    def _make_prop(self, source):
        source.propagation = Propagation(prop_type=u'Seed')

        # a propagation doesn't normally have _seed and _cutting but
        # it's ok here for the test
        seed = PropSeed(**default_seed_values)
        seed.propagation = source.propagation
        cutting = PropCutting(**default_cutting_values)
        cutting.propagation = source.propagation
        self.session.commit()
        prop_id = source.propagation.id
        seed_id = source.propagation._seed.id
        cutting_id = source.propagation._cutting.id
        return prop_id, seed_id, cutting_id

    def test_propagation(self):
        """
        Test cascading for the Source.propagation relation
        """
        source = Source()
        self.accession.source = source
        prop_id, seed_id, cutting_id = self._make_prop(source)
        self.session.commit()
        source.propagation = None
        self.session.commit()
        self.assert_(seed_id)
        self.assert_(cutting_id)
        self.assert_(prop_id)
        # make sure the propagation got cleaned up when the
        # source.propagation attribute was set to None
        self.assert_(not self.session.query(PropSeed).get(seed_id))
        self.assert_(not self.session.query(PropCutting).get(cutting_id))
        self.assert_(not self.session.query(Propagation).get(prop_id))

    def test(self):
        """
        Test bauble.plugins.garden.Source and related properties
        """
        source = Source()
        #self.assert_(hasattr(source, 'plant_propagation'))

        location = Location(code=u'1', name=u'site1')
        plant = Plant(accession=self.accession, location=location, code=u'1',
                      quantity=1)
        plant.propagations.append(Propagation(prop_type=u'Seed'))
        self.session.commit()

        source.source_detail = SourceDetail()
        source.source_detail.name = u'name'
        source.sources_code = u'1'
        source.collection = Collection(locale=u'locale')
        source.propagation = Propagation(prop_type=u'Seed')
        source.plant_propagation = plant.propagations[0]
        source.accession = self.accession  # test source's accession property
        self.session.commit()

        # test that cascading works properly
        source_detail_id = source.source_detail.id
        coll_id = source.collection.id
        prop_id = source.propagation.id
        plant_prop_id = source.plant_propagation.id
        self.accession.source = None  # tests the accessions source
        self.session.commit()

        # the Colection and Propagation should be
        # deleted since they are specific to the source
        self.assert_(not self.session.query(Collection).get(coll_id))
        self.assert_(not self.session.query(Propagation).get(prop_id))

        # the SourceDetail and plant Propagation shouldn't be deleted
        # since they are independent of the source
        self.assert_(self.session.query(Propagation).get(plant_prop_id))
        self.assert_(self.session.query(SourceDetail).get(source_detail_id))

    def test_details_editor(self):
        raise SkipTest('separate view from presenter, then test presenter')
        e = SourceDetailEditor()
        e.start()


class AccessionTests(GardenTestCase):

    def __init__(self, *args):
        super(AccessionTests, self).__init__(*args)

    def setUp(self):
        super(AccessionTests, self).setUp()

    def tearDown(self):
        super(AccessionTests, self).tearDown()

    def test_species_str(self):
        """
        Test Accession.species_str()
        """
        acc = self.create(Accession, species=self.species, code=u'1')
        s = u'Echinocactus grusonii'
        sp_str = acc.species_str()
        self.assert_(s == sp_str, '%s == %s' % (s, sp_str))
        acc.id_qual = '?'
        s = u'Echinocactus grusonii(?)'
        sp_str = acc.species_str()
        self.assert_(s == sp_str, '%s == %s' % (s, sp_str))

        acc.id_qual = 'aff.'
        acc.id_qual_rank = u'sp'
        s = u'Echinocactus aff. grusonii'
        sp_str = acc.species_str()
        self.assert_(s == sp_str, '%s == %s' % (s, sp_str))

        # here species.infrasp is None but we still allow the string
        acc.id_qual = 'cf.'
        acc.id_qual_rank = 'infrasp'
        s = u'Echinocactus grusonii cf.'  # ' None'
        sp_str = acc.species_str()
        self.assert_(s == sp_str, '%s == %s' % (s, sp_str))

        # species.infrasp is still none but these just get pasted on
        # the end so it doesn't matter
        acc.id_qual = 'incorrect'
        acc.id_qual_rank = 'infrasp'
        s = u'Echinocactus grusonii(incorrect)'
        sp_str = acc.species_str()
        self.assert_(s == sp_str, '%s == %s' % (s, sp_str))

        acc.id_qual = 'forsan'
        acc.id_qual_rank = u'sp'
        s = u'Echinocactus grusonii(forsan)'
        sp_str = acc.species_str()
        self.assert_(s == sp_str, '%s == %s' % (s, sp_str))

        acc.species.set_infrasp(1, u'cv.', u'Cultivar')
        acc.id_qual = u'cf.'
        acc.id_qual_rank = u'infrasp'
        s = u"Echinocactus grusonii cf. 'Cultivar'"
        sp_str = acc.species_str()
        self.assert_(s == sp_str, '%s == %s' % (s, sp_str))

        # test that the cached string is returned

        # have to commit because the cached string won't be returned
        # on dirty species
        self.session.commit()
        s2 = acc.species_str()
        assert id(sp_str) == id(s2), '%s(%s) == %s(%s)' % (sp_str, id(sp_str),
                                                           s2, id(s2))

        # this used to test that if the id_qual was set but the
        # id_qual_rank wasn't then we would get an error. now we just
        # show an warning and put the id_qual on the end of the string
#         acc.id_qual = 'aff.'
#         acc.id_qual_rank = None
#         self.assertRaises(CheckConditionError, acc.species_str)

    def test_delete(self):
        """
        Test that when an accession is deleted any orphaned rows are
        cleaned up.
        """
        acc = self.create(Accession, species=self.species, code=u'1')
        plant = self.create(Plant, accession=acc, quantity=1,
                            location=Location(name=u'site', code=u'STE'),
                            code=u'1')
        self.session.commit()

        # test that the plant is deleted after being orphaned
        plant_id = plant.id
        self.session.delete(acc)
        self.session.commit()
        self.assert_(not self.session.query(Plant).get(plant_id))

    def test_constraints(self):
        """
        Test the constraints on the accession table.
        """
        acc = Accession(species=self.species, code=u'1')
        self.session.add(acc)
        self.session.commit()

        # test that accession.code is unique
        acc = Accession(species=self.species, code=u'1')
        self.session.add(acc)
        self.assertRaises(IntegrityError, self.session.commit)

    def test_accession_source_editor(self, accession=None):
        acc = self.create(Accession, species=self.species, code=u'parent')
        plant = self.create(Plant, accession=acc, quantity=1,
                            location=Location(name=u'site', code=u'STE'),
                            code=u'1')
        # creating a dummy propagtion without a related seed/cutting
        prop = self.create(Propagation, prop_type=u'Seed')
        plant.propagations.append(prop)
        self.session.commit()
        plant_prop_id = prop.id
        assert plant_prop_id  # assert we got a valid id after the commit

        acc = Accession(code=u'code', species=self.species)
        self.editor = AccessionEditor(acc)
        # normally called by editor.presenter.start() but we don't call it here
        self.editor.presenter.source_presenter.start()
        widgets = self.editor.presenter.view.widgets
        update_gui()

        # set the date so the presenter will be "dirty"
        widgets.acc_date_recvd_entry.props.text = utils.today_str()

        # set the source type as "Garden Propagation"
        widgets.acc_source_comboentry.child.props.text = \
            SourcePresenter.garden_prop_str
        assert not self.editor.presenter.problems

        # set the source plant
        widgets.source_prop_plant_entry.props.text = str(plant)
        update_gui()
        comp = widgets.source_prop_plant_entry.get_completion()
        comp.emit('match-selected', comp.get_model(),
                  comp.get_model().get_iter_first())

        # assert that the propagations were added to the treevide
        treeview = widgets.source_prop_treeview
        assert treeview.get_model()

        # select the first/only propagation in the treeview
        toggle_cell = widgets.prop_toggle_cell.emit('toggled', 0)
        self.assertTrue(toggle_cell is None)

        # commit the changes and cleanup
        self.editor.handle_response(gtk.RESPONSE_OK)
        self.editor.session.close()

        # open a seperate session and make sure everything committed
        session = db.Session()
        acc = session.query(Accession).filter_by(code=u'code')[0]
        parent = session.query(Accession).filter_by(code=u'parent')[0]
        self.assertTrue(parent is not None)
        assert acc.source.plant_propagation_id == plant_prop_id

    def test_accession_editor(self):
        acc = Accession(code=u'code', species=self.species)
        self.editor = AccessionEditor(acc)
        update_gui()

        widgets = self.editor.presenter.view.widgets
        # make sure there is a problem if the species entry text isn't
        # a species string
        widgets.acc_species_entry.set_text('asdasd')
        assert self.editor.presenter.problems

        # make sure the problem is removed if the species entry text
        # is set to a species string

        # fill in the completions
        widgets.acc_species_entry.set_text(str(self.species)[0:3])
        update_gui()  # ensures idle callback is called to add completions
        # set the fill string which should match from completions
        widgets.acc_species_entry.set_text(str(self.species))
        assert not self.editor.presenter.problems, \
            self.editor.presenter.problems

        # commit the changes and cleanup
        self.editor.model.name = u'asda'
        import gtk
        self.editor.handle_response(gtk.RESPONSE_OK)
        self.editor.session.close()

    def test_editor(self):
        """
        Interactively test the AccessionEditor
        """
        raise SkipTest('separate view from presenter, then test presenter')
        #donor = self.create(Donor, name=u'test')
        sp2 = Species(genus=self.genus, sp=u'species')
        sp2.synonyms.append(self.species)
        self.session.add(sp2)
        self.session.commit()
        # import datetime again since sometimes i get an weird error
        import datetime
        acc_code = '%s%s1' % (
            datetime.date.today().year, Plant.get_delimiter())
        acc = self.create(Accession, species=self.species, code=acc_code)
        voucher = Voucher(herbarium=u'abcd', code=u'123')
        acc.vouchers.append(voucher)

        def mem(size="rss"):
            """Generalization; memory sizes: rss, rsz, vsz."""
            import os
            return int(os.popen('ps -p %d -o %s | tail -1' %
                       (os.getpid(), size)).read())

        # add verificaiton
        ver = Verification()
        ver.verifier = u'me'
        ver.date = datetime.date.today()
        ver.prev_species = self.species
        ver.species = self.species
        ver.level = 1
        acc.verifications.append(ver)

        location = Location(name=u'loc1', code=u'loc1')
        plant = Plant(accession=acc, location=location, code=u'1', quantity=1)
        prop = Propagation(prop_type=u'Seed')
        seed = PropSeed(**default_seed_values)
        seed.propagation = prop
        plant.propagations.append(prop)

        source_detail = SourceDetail(name=u'Test Source',
                                     source_type=u'Expedition')
        source = Source(sources_code=u'22')
        source.source_detail = source_detail
        acc.source = source

        self.session.commit()

        self.editor = AccessionEditor(model=acc)
        try:
            self.editor.start()
        except Exception, e:
            import traceback
            logger.debug(traceback.format_exc(0))
            logger.debug(e)


class VerificationTests(GardenTestCase):

    def __init__(self, *args):
        super(VerificationTests, self).__init__(*args)

    def setUp(self):
        super(VerificationTests, self).setUp()

    def tearDown(self):
        super(VerificationTests, self).tearDown()

    def test_verifications(self):
        acc = self.create(Accession, species=self.species, code=u'1')
        self.session.add(acc)
        self.session.commit()

        ver = Verification()
        ver.verifier = u'me'
        ver.date = datetime.date.today()
        ver.level = 1
        ver.species = acc.species
        ver.prev_species = acc.species
        acc.verifications.append(ver)
        try:
            self.session.commit()
        except Exception, e:
            logger.debug(e)
            self.session.rollback()
        self.assert_(ver in acc.verifications)
        self.assert_(ver in self.session)


class LocationTests(GardenTestCase):

    def __init__(self, *args):
        super(LocationTests, self).__init__(*args)

    def setUp(self):
        super(LocationTests, self).setUp()

    def tearDown(self):
        super(LocationTests, self).tearDown()

    def test_location_editor(self):
        loc = self.create(Location, name=u'some site', code=u'STE')
        self.session.commit()
        editor = LocationEditor(model=loc)
        update_gui()
        widgets = editor.presenter.view.widgets

        # test that the accept buttons are NOT sensitive since nothing
        # has changed and that the text entries and model are the same
        self.assertEquals(widgets.loc_name_entry.get_text(), loc.name)
        self.assertEquals(widgets.loc_code_entry.get_text(), loc.code)
        self.assertFalse(widgets.loc_ok_button.props.sensitive)
        self.assertFalse(widgets.loc_next_button.props.sensitive)

        # test the accept buttons become sensitive when the name entry
        # is changed
        widgets.loc_name_entry.set_text('something')
        update_gui()
        self.assertTrue(widgets.loc_ok_button.props.sensitive)
        self.assertTrue(widgets.loc_ok_and_add_button.props.sensitive)
        self.assertTrue(widgets.loc_next_button.props.sensitive)

        # test the accept buttons become NOT sensitive when the code
        # entry is empty since this is a required field
        widgets.loc_code_entry.set_text('')
        update_gui()
        self.assertFalse(widgets.loc_ok_button.props.sensitive)
        self.assertFalse(widgets.loc_ok_and_add_button.props.sensitive)
        self.assertFalse(widgets.loc_next_button.props.sensitive)

        # test the accept buttons aren't sensitive from setting the textview
        buff = gtk.TextBuffer()
        buff.set_text('saasodmadomad')
        widgets.loc_desc_textview.set_buffer(buff)
        self.assertFalse(widgets.loc_ok_button.props.sensitive)
        self.assertFalse(widgets.loc_ok_and_add_button.props.sensitive)
        self.assertFalse(widgets.loc_next_button.props.sensitive)

        # commit the changes and cleanup
        editor.model.name = editor.model.code = u'asda'
        editor.handle_response(gtk.RESPONSE_OK)
        editor.session.close()
        editor.presenter.cleanup()
        del editor

        self.assertEquals(utils.gc_objects_by_type('LocationEditor'), [],
                          'LocationEditor not deleted')
        self.assertEquals(
            utils.gc_objects_by_type('LocationEditorPresenter'), [],
            'LocationEditorPresenter not deleted')
        self.assertEquals(utils.gc_objects_by_type('LocationEditorView'), [],
                          'LocationEditorView not deleted')

    def test_editor(self):
        """
        Interactively test the PlantEditor
        """
        raise SkipTest('separate view from presenter, then test presenter')
        loc = self.create(Location, name=u'some site', code=u'STE')
        editor = LocationEditor(model=loc)
        editor.start()
        del editor
        assert utils.gc_objects_by_type('LocationEditor') == [], \
            'LocationEditor not deleted'
        assert utils.gc_objects_by_type('LocationEditorPresenter') == [], \
            'LocationEditorPresenter not deleted'
        assert utils.gc_objects_by_type('LocationEditorView') == [], \
            'LocationEditorView not deleted'


# class CollectionTests(GardenTestCase):

#     def __init__(self, *args):
#         super(CollectionTests, self).__init__(*args)

#     def setUp(self):
#         super(CollectionTests, self).setUp()

#     def tearDown(self):
#         super(CollectionTests, self).tearDown()

#     def test_accession_prop(self):
#         """
#         Test Collection.accession property
#         """
#         acc = Accession(code=u'1', species=self.species)
#         collection = Collection(locale=u'some locale')
#         self.session.add_all((acc, collection))

#         self.assert_(acc.source is None)
#         collection.accession = acc
#         self.assert_(acc._collection == collection, acc._collection)
#         self.assert_(acc.source_type == 'Collection')
#         self.assert_(acc.source == collection)
#         self.session.commit()


class InstitutionTests(GardenTestCase):

    # TODO: create a non interactive tests that starts the
    # InstututionEditor and checks that it doesn't leak memory

    def test_editor(self):
        raise SkipTest('separate view from presenter, then test presenter')
        e = InstitutionEditor()
        e.start()


# latitude: deg[0-90], min[0-59], sec[0-59]
# longitude: deg[0-180], min[0-59], sec[0-59]

ALLOWED_DECIMAL_ERROR = 5
THRESHOLD = .01

# indexs into conversion_test_date
DMS = 0  # DMS
DEG_MIN_DEC = 1  # Deg with minutes decimal
DEG_DEC = 2  # Degrees decimal
UTM = 3  # Datum(wgs84/nad83 or nad27), UTM Zone, Easting, Northing

# decimal points to accuracy in decimal degrees
# 1 +/- 8000m
# 2 +/- 800m
# 3 +/- 80m
# 4 +/- 8m
# 5 +/- 0.8m
# 6 +/- 0.08m

from decimal import Decimal
dec = Decimal
conversion_test_data = (((('N', 17, 21, dec(59)),  # dms
                          ('W', 89, 1, 41)),
                         ((dec(17), dec('21.98333333')),  # deg min_dec
                          (dec(-89), dec('1.68333333'))),
                         (dec('17.366389'), dec('-89.028056')),  # dec deg
                         (('wgs84', 16, 284513, 1921226))),  # utm
                        \
                        ((('S', 50, 19, dec('32.59')),  # dms
                          ('W', 74, 2, dec('11.6'))),
                         ((dec(-50), dec('19.543166')),  # deg min_dec
                          (dec(-74), dec('2.193333'))),
                         (dec('-50.325719'), dec('-74.036556')),  # dec deg
                         (('wgs84', 18, 568579, 568579)),
                         (('nad27', 18, 568581, 4424928))),
                        \
                        ((('N', 9, 0, dec('4.593384')),
                          ('W', 78, 3, dec('28.527984'))),
                         ((9, dec('0.0765564')),
                          (-78, dec('3.4754664'))),
                         (dec('9.00127594'), dec('-78.05792444'))),
                        \
                        ((('N', 49, 10, 28),
                          ('W', 121, 40, 39)),
                         ((49, dec('10.470')),
                          (-121, dec('40.650'))),
                         (dec('49.174444'), dec('-121.6775')))
                        )


parse_lat_lon_data = ((('N', '17 21 59'), dec('17.366389')),
                      (('N', '17 21.983333'), dec('17.366389')),
                      (('N', '17.03656'), dec('17.03656')),
                      (('W', '89 1 41'), dec('-89.028056')),
                      (('W', '89 1.68333333'), dec('-89.028056')),
                      (('W', '-89 1.68333333'), dec('-89.028056')),
                      (('E', '121 40 39'), dec('121.6775')))


class DMSConversionTests(unittest.TestCase):

    # test coordinate conversions
    def test_dms_to_decimal(self):
        # test converting DMS to degrees decimal
        ALLOWED_ERROR = 6
        for data_set in conversion_test_data:
            dms_data = data_set[DMS]
            dec_data = data_set[DEG_DEC]
            lat_dec = dms_to_decimal(*dms_data[0])
            lon_dec = dms_to_decimal(*dms_data[1])
            self.assertAlmostEqual(lat_dec, dec_data[0], ALLOWED_ERROR)
            self.assertAlmostEqual(lon_dec, dec_data[1], ALLOWED_ERROR)

    def test_decimal_to_dms(self):
        # test converting degrees decimal to dms, allow a certain
        # amount of error in the seconds
        ALLOWABLE_ERROR = 2
        for data_set in conversion_test_data:
            dms_data = data_set[DMS]
            dec_data = data_set[DEG_DEC]

            # convert to DMS
            lat_dms = latitude_to_dms(dec_data[0])
            self.assertEqual(lat_dms[0:2], dms_data[0][0:2])
            # test seconds with allowable error
            self.assertAlmostEqual(lat_dms[3], dms_data[0][3], ALLOWABLE_ERROR)

            lon_dms = longitude_to_dms(dec_data[1])
            self.assertEqual(lon_dms[0:2], dms_data[1][0:2])
            # test seconds with allowable error
            self.assertAlmostEqual(lon_dms[3], dms_data[1][3], ALLOWABLE_ERROR)

    def test_parse_lat_lon(self):
        parse = CollectionPresenter._parse_lat_lon
        for data, dec in parse_lat_lon_data:
            result = parse(*data)
            self.assert_(result == dec, '%s: %s == %s' % (data, result, dec))


class FromAndToDictTest(GardenTestCase):
    """tests the retrieve_or_create and the as_dict methods
    """

    def test_add_accession_at_species_rank(self):
        acc = Accession.retrieve_or_create(
            self.session, {'code': u'010203',
                           'rank': 'species',
                           'taxon': u'Echinocactus grusonii'})
        self.assertEquals(acc.species, self.species)

    def test_add_accession_at_genus_rank(self):
        acc = Accession.retrieve_or_create(
            self.session, {'code': u'010203',
                           'rank': 'genus',
                           'taxon': u'Echinocactus'})
        self.assertEquals(acc.species.genus, self.genus)

    def test_add_plant(self):
        acc = Accession.retrieve_or_create(
            self.session, {'code': u'010203',
                           'rank': 'species',
                           'taxon': u'Echinocactus grusonii'})
        plt = Plant.retrieve_or_create(
            self.session, {'accession': u'010203',
                           'code': u'1',
                           'location': u'wrong one',
                           'quantity': 1})
        self.assertEquals(plt.accession, acc)

    def test_set_create_timestamp_european(self):
        from datetime import datetime
        ## insert an object with a timestamp
        Location.retrieve_or_create(
            self.session, {'code': u'1',
                           '_created': '10/12/2001'})
        ## retrieve same object from other session
        session = db.Session()
        loc = Location.retrieve_or_create(session, {'code': u'1', })
        self.assertEquals(loc._created, datetime(2001, 12, 10))

    def test_set_create_timestamp_iso8601(self):
        from datetime import datetime
        ## insert an object with a timestamp
        Location.retrieve_or_create(
            self.session, {'code': u'1',
                           '_created': '2001-12-10'})
        ## retrieve same object from other session
        session = db.Session()
        loc = Location.retrieve_or_create(session, {'code': u'1', })
        self.assertEquals(loc._created, datetime(2001, 12, 10))


class FromAndToDict_create_update_test(GardenTestCase):
    "test the create and update fields in retrieve_or_create"

    def setUp(self):
        GardenTestCase.setUp(self)
        acc = Accession(species=self.species, code=u'010203')
        loc = Location(code=u'123')
        loc2 = Location(code=u'213')
        plt = Plant(accession=acc, code=u'1', quantity=1, location=loc)
        self.session.add_all([acc, loc, loc2, plt])
        self.session.commit()

    def test_accession_nocreate_noupdate_noexisting(self):
        # do not create if not existing
        acc = Accession.retrieve_or_create(
            self.session, {'code': u'030201',
                           'rank': 'species',
                           'taxon': u'Echinocactus texelensis'},
            create=False)
        self.assertEquals(acc, None)

    def test_accession_nocreate_noupdateeq_existing(self):
        ## retrieve same object, we only give the keys
        acc = Accession.retrieve_or_create(
            self.session, {'code': u'010203'},
            create=False, update=False)
        self.assertTrue(acc is not None)
        self.assertEquals(acc.species, self.species)

    def test_accession_nocreate_noupdatediff_existing(self):
        ## do not update object with new data
        acc = Accession.retrieve_or_create(
            self.session, {'code': u'010203',
                           'rank': 'species',
                           'taxon': u'Echinocactus texelensis'},
            create=False, update=False)
        self.assertEquals(acc.species, self.species)

    def test_accession_nocreate_updatediff_existing(self):
        ## update object in self.session
        acc = Accession.retrieve_or_create(
            self.session, {'code': u'010203',
                           'rank': 'species',
                           'taxon': u'Echinocactus texelensis'},
            create=False, update=True)
        self.assertEquals(acc.species, self.sp2)

    def test_plant_nocreate_noupdate_noexisting(self):
        # do not create if not existing
        plt = Plant.retrieve_or_create(
            self.session, {'accession': u'010203',
                           'code': u'2',
                           'quantity': 1,
                           'location': u'123'},
            create=False)
        self.assertEquals(plt, None)

    def test_plant_nocreate_noupdateeq_existing(self):
        ## retrieve same object, we only give the keys
        plt = Plant.retrieve_or_create(
            self.session, {'accession': u'010203',
                           'code': u'1'},
            create=False, update=False)
        self.assertTrue(plt is not None)
        self.assertEquals(plt.quantity, 1)

    def test_plant_nocreate_noupdatediff_existing(self):
        ## do not update object with new data
        plt = Plant.retrieve_or_create(
            self.session, {'accession': u'010203',
                           'code': u'1',
                           'quantity': 3},
            create=False, update=False)
        self.assertTrue(plt is not None)
        self.assertEquals(plt.quantity, 1)

    def test_plant_nocreate_updatediff_existing(self):
        ## update object in self.session
        plt = Plant.retrieve_or_create(
            self.session, {'accession': u'010203',
                           'code': u'1',
                           'quantity': 3},
            create=False, update=True)
        self.assertTrue(plt is not None)
        self.assertEquals(plt.quantity, 3)
        self.assertEquals(plt.location.code, '123')
        plt = Plant.retrieve_or_create(
            self.session, {'accession': u'010203',
                           'code': u'1',
                           'location': u'213'},
            create=False, update=True)
        self.assertTrue(plt is not None)
        self.assertTrue(plt.location is not None)
        self.assertEquals(plt.location.code, u'213')


class AccessionNotesSerializeTest(GardenTestCase):
    ## for the sake of retrieve_or_update, we consider as keys:
    ## accession, category, and date.

    def setUp(self):
        GardenTestCase.setUp(self)
        acc = Accession(species=self.species, code=u'010203')
        self.session.add(acc)
        self.session.flush()
        note1 = AccessionNote(accession=acc, category=u'factura',
                              date='2014-01-01', note=u'992288')
        note2 = AccessionNote(accession=acc, category=u'foto',
                              date='2014-01-01', note=u'file://')
        self.session.add_all([note1, note2])
        self.session.commit()

    def test_accession_note_nocreate_noupdate_noexisting(self):
        # do not create if not existing
        obj = AccessionNote.retrieve_or_create(
            self.session, {'object': 'accession_note',
                           'accession': u'010203',
                           'category': u'newcat',
                           'date': '2014-01-01',
                           },
            create=False)
        self.assertTrue(obj is None)

    def test_accession_note_nocreate_noupdateeq_existing(self):
        ## retrieve same object, we only give the keys
        obj = AccessionNote.retrieve_or_create(
            self.session, {'object': 'accession_note',
                           'accession': u'010203',
                           'category': u'foto',
                           'date': '2014-01-01',
                           },
            create=False)
        self.assertTrue(obj is not None)
        self.assertEquals(obj.note, u"file://")

    def test_accession_note_nocreate_noupdatediff_existing(self):
        ## do not update object with new data
        obj = AccessionNote.retrieve_or_create(
            self.session, {'object': 'accession_note',
                           'accession': u'010203',
                           'category': u'foto',
                           'date': '2014-01-01',
                           'note': 'url://'
                           },
            create=False, update=False)
        self.assertTrue(obj is not None)
        self.assertEquals(obj.note, u"file://")

    def test_accession_note_nocreate_updatediff_existing(self):
        ## update object in self.session
        obj = AccessionNote.retrieve_or_create(
            self.session, {'object': 'accession_note',
                           'accession': u'010203',
                           'category': u'foto',
                           'date': '2014-01-01',
                           'note': 'url://'
                           },
            create=False, update=True)
        self.assertTrue(obj is not None)
        self.assertEquals(obj.note, u"url://")

import bauble.search as search


class PlantSearchTest(GardenTestCase):
    def __init__(self, *args):
        super(PlantSearchTest, self).__init__(*args)

    def setUp(self):
        super(PlantSearchTest, self).setUp()
        setUp_data()

    def test_searchbyplantcode(self):
        raise SkipTest('should really work, please inspect')
        mapper_search = search.get_strategy('MapperSearch')

        results = mapper_search.search('1.1.1', self.session)
        self.assertEquals(len(results), 1)
        p = results.pop()
        ex = self.session.query(Plant).filter(Plant.id == 1).first()
        self.assertEqual(p, ex)
        results = mapper_search.search('2.2.1', self.session)
        logger.debug(results)
        self.assertEquals(len(results), 1)
        p = results.pop()
        ex = self.session.query(Plant).filter(Plant.id == 2).first()
        self.assertEqual(p, ex)
        results = mapper_search.search('2.2.2', self.session)
        self.assertEquals(len(results), 1)
        p = results.pop()
        ex = self.session.query(Plant).filter(Plant.id == 3).first()
        self.assertEqual(p, ex)

    def test_searchbyaccessioncode(self):
        mapper_search = search.get_strategy('MapperSearch')

        results = mapper_search.search('2001.1', self.session)
        self.assertEquals(len(results), 1)
        a = results.pop()
        expect = self.session.query(Accession).filter(
            Accession.id == 1).first()
        logger.debug("%s, %s" % (a, expect))
        self.assertEqual(a, expect)
        results = mapper_search.search('2001.2', self.session)
        self.assertEquals(len(results), 1)
        a = results.pop()
        expect = self.session.query(Accession).filter(
            Accession.id == 2).first()
        logger.debug("%s, %s" % (a, expect))
        self.assertEqual(a, expect)


from bauble.plugins.garden.accession import get_next_code
from bauble.plugins.garden.location import mergevalues


class GlobalFunctionsTests(GardenTestCase):
    def test_get_next_code_first_this_year(self):
        this_year = str(datetime.date.today().year)
        self.assertEquals(get_next_code(), this_year + '.0001')

    def test_get_next_code_second_this_year(self):
        this_year = str(datetime.date.today().year)
        this_code = get_next_code()
        acc = Accession(species=self.species, code=this_code)
        self.session.add(acc)
        self.session.flush()
        self.assertEquals(get_next_code(), this_year + '.0002')

    def test_get_next_code_absolute_beginning(self):
        this_year = str(datetime.date.today().year)
        self.session.query(Accession).delete()
        self.session.flush()
        self.assertEquals(get_next_code(), this_year + '.0001')

    def test_get_next_code_next_with_hole(self):
        this_year = str(datetime.date.today().year)
        this_code = this_year + u'.0050'
        acc = Accession(species=self.species, code=this_code)
        self.session.add(acc)
        self.session.flush()
        self.assertEquals(get_next_code(), this_year + '.0051')

    def test_mergevalues_equal(self):
        'if the values are equal, return it'
        self.assertEquals(mergevalues('1', '1', '%s|%s'), '1')

    def test_mergevalues_conflict(self):
        'if they conflict, return both'
        self.assertEquals(mergevalues('2', '1', '%s|%s'), '2|1')

    def test_mergevalues_one_empty(self):
        'if one is empty, return the non empty one'
        self.assertEquals(mergevalues('2', None, '%s|%s'), '2')
        self.assertEquals(mergevalues(None, '2', '%s|%s'), '2')
        self.assertEquals(mergevalues('2', '', '%s|%s'), '2')

    def test_mergevalues_both_empty(self):
        'if both are empty, return the empty string'
        self.assertEquals(mergevalues(None, None, '%s|%s'), '')
