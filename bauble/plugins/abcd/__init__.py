# -*- coding: utf-8 -*-
#
# Copyright (c) 2005,2006,2007,2008,2009 Brett Adams <brett@belizebotanic.org>
# Copyright (c) 2012-2015 Mario Frasca <mario@anche.no>
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
# -*- coding: utf-8 -*-
#
#
# ABCD import/exporter
#

import os
import csv

import gtk

from sqlalchemy import *
from sqlalchemy.orm import *

import bauble
import bauble.db as db
from bauble.error import check, CheckConditionError
import bauble.paths as paths
import bauble.utils as utils
import bauble.pluginmgr as pluginmgr
from bauble.plugins.plants.species_model import Species
from bauble.plugins.garden.plant import Plant
from bauble.plugins.garden.accession import Accession

# NOTE: see biocase provider software for reading and writing ABCD data
# files, already downloaded software to desktop

# TODO: should have a command line argument to create labels without starting
# the full bauble interface, after creating the labels it should automatically
# open the whatever ever view is associated with pdf files
# e.g bauble -labels "select string"
# bauble -labels "block=4"
# bauble -label "acc=1997"
#
# TODO: create label make in the tools that show a dialog with an entry
# the entry is for a search string that then returns a list of all the labels
# that'll be made with checkboxess next to them to de/select the ones you
# don't want to print, could also have a check box to select species or
# accessions so we can print labels for plants that don't have accessions,
# though this could be a problem b/c abcd data expects 'unitid' fields but
# we could have a special case just for generating labels
#

def validate_xml(root):
    """
    Validate root against ABCD 2.06 schema

    :param root: root of an XML tree to validate against
    :returns: True or False depending if root validates correctly
    """
    schema_file = os.path.join(paths.lib_dir(), 'plugins',
            'abcd','abcd_2.06.xsd')
    xmlschema_doc = etree.parse(schema_file)
    abcd_schema = etree.XMLSchema(xmlschema_doc)
    return abcd_schema.validate(root)

# TODO: this function needs to be renamed since we now check an object in
# the list is an Accession them we use the accession data as the UnitID, else
# we treat it as a Plant...using plants is necessary for things like making
# labels but most likely accessions are wanted if we're exchanging data, the
# only problem is that accessions don't keep status, like dead, etc.

def verify_institution(institution):
    test = lambda x: x != '' and x != None
    return test(institution.inst_name) and \
        test(institution.inst_technical_contact) and \
        test(institution.inst_email) and test(institution.inst_contact) and \
        test(institution.inst_code)


namespaces = {'abcd': 'http://www.tdwg.org/schemas/abcd/2.06'}


def ABCDElement(parent, name, text=None, attrib=None):
    """
    A factory function to create an ABCDElement, must be a subelement.

    :param parent: an element
    :param name: a string, the name of the new element
    :param text: the text attribue to set on the new element
    :param attrib: any additional attributes for the new element
    """
    if attrib is None:
        attrib = {}
    el = SubElement(parent, '{%s}%s' % (namespaces['abcd'], name),
                   nsmap=namespaces, attrib=attrib)
    el.text = text
    return el


def DataSets():
    """
    """
    return Element('{%s}DataSets' % namespaces['abcd'], nsmap=namespaces)


class ABCDAdapter(object):
    """
    An abstract base class for creating ABCD adapters.
    """
    # TODO: create a HigherTaxonRank/HigherTaxonName iteratorator for a list
    # of all the higher taxon

    # TODO: need to mark those fields that are required and those that
    # are optional
    def extra_elements(self, unit):
        """
        Add extra non required elements
        """
        pass

    def __init__(self, obj):
        self._object = obj

    def get_UnitID(self):
        """
        Get a value for the UnitID
        """
        pass

    def get_family(self):
        """
        Get a value for the family.
        """
        pass

    def get_FullScientificNameString(self, authors=True):
        """
        Get the full scientific name string.
        """
        pass

    def get_GenusOrMonomial(self):
        """
        Get the Genus string.
        """
        pass

    def get_FirstEpithet(self):
        """
        Get the first epithet.
        """
        pass

    def get_AuthorTeam(self):
        """
        Get the Author string.
        """
        pass

    def get_InformalNameString(self):
        """
        Get the common name string.
        """
        pass



def create_abcd(decorated_objects, authors=True, validate=True):
    """
    :param objects: a list/tuple of objects that implement the ABCDDecorator
      interface
    :param authors: flag to control whether to include the authors in the
      species name
    :param validate: whether we should validate the data before returning
    :returns: a valid ABCD ElementTree
    """
    import bauble.plugins.garden.institution as institution
    inst = institution.Institution()
    if not verify_institution(inst):
        msg = _('Some or all of the information about your institution or ' \
                'business is not complete. Please make sure that the ' \
                'Name, Technical Contact, Email, Contact and Institution '
                'Code fields are filled in.')
        utils.message_dialog(msg)
        institution.InstitutionEditor().start()
        return create_abcd(decorated_objects, authors, validate)

    datasets = DataSets()
    ds = ABCDElement(datasets, 'DataSet')
    tech_contacts = ABCDElement(ds, 'TechnicalContacts')
    tech_contact = ABCDElement(tech_contacts, 'TechnicalContact')

    # TODO: need to include contact information in bauble meta when
    # creating a new database
    ABCDElement(tech_contact, 'Name', text=inst.inst_technical_contact)
    ABCDElement(tech_contact, 'Email', text=inst.inst_email)
    cont_contacts = ABCDElement(ds, 'ContentContacts')
    cont_contact = ABCDElement(cont_contacts, 'ContentContact')
    ABCDElement(cont_contact, 'Name', text=inst.inst_contact)
    ABCDElement(cont_contact, 'Email', text=inst.inst_email)
    metadata = ABCDElement(ds, 'Metadata', )
    description = ABCDElement(metadata, 'Description')

    # TODO: need to get the localized language
    representation = ABCDElement(description, 'Representation',
                                    attrib={'language': 'en'})
    revision = ABCDElement(metadata, 'RevisionData')
    ABCDElement(revision, 'DateModified', text='2001-03-01T00:00:00')
    title = ABCDElement(representation, 'Title', text='TheTitle')
    units = ABCDElement(ds, 'Units')

    # build the ABCD unit
    for obj in decorated_objects:
        unit = ABCDElement(units, 'Unit')
        ABCDElement(unit, 'SourceInstitutionID', text=inst.inst_code)

        # TODO: don't really understand the SourceID element
        ABCDElement(unit, 'SourceID', text='Bauble')

        unit_id = ABCDElement(unit, 'UnitID', text=obj.get_UnitID())
        ABCDElement(unit, 'DateLastEdited', text=obj.get_DateLastEdited())

        # TODO: add list of verifications to Identifications

        # scientific name identification
        identifications = ABCDElement(unit, 'Identifications')
        identification = ABCDElement(identifications, 'Identification')
        result = ABCDElement(identification, 'Result')
        taxon_identified = ABCDElement(result, 'TaxonIdentified')
        higher_taxa = ABCDElement(taxon_identified, 'HigherTaxa')
        higher_taxon = ABCDElement(higher_taxa, 'HigherTaxon')

        # TODO: ABCDDecorator should provide an iterator so that we can
        # have multiple HigherTaxonName's
        higher_taxon_name = ABCDElement(higher_taxon, 'HigherTaxonName',
                                        text=obj.get_family())
        higher_taxon_rank = ABCDElement(higher_taxon, 'HigherTaxonRank',
                                        text='familia')

        scientific_name = ABCDElement(taxon_identified, 'ScientificName')
        ABCDElement(scientific_name, 'FullScientificNameString',
                       text=obj.get_FullScientificNameString(authors))

        name_atomised = ABCDElement(scientific_name, 'NameAtomised')
        botanical = ABCDElement(name_atomised, 'Botanical')
        ABCDElement(botanical, 'GenusOrMonomial',
                       text=obj.get_GenusOrMonomial())
        ABCDElement(botanical, 'FirstEpithet', text=obj.get_FirstEpithet())
        author_team = obj.get_AuthorTeam()
        if author_team is not None:
            ABCDElement(botanical, 'AuthorTeam', text=author_team)
        ABCDElement(identification, 'PreferredFlag', text='true')

        # vernacular name identification
        # TODO: should we include all the vernacular names or only the default
        # one
        vernacular_name = obj.get_InformalNameString()
        if vernacular_name is not None:
            identification = ABCDElement(identifications, 'Identification')
            result = ABCDElement(identification, 'Result')
            taxon_identified = ABCDElement(result, 'TaxonIdentified')
            ABCDElement(taxon_identified, 'InformalNameString',
                           text=vernacular_name)

        # add all the extra non standard elements
        obj.extra_elements(unit)
        # TODO: handle verifiers/identifiers
        # TODO: RecordBasis

        # notes are last in the schema and extra_elements() shouldn't
        # add anything that comes past Notes, e.g. RecordURI,
        # EAnnotations, UnitExtension
        notes = obj.get_Notes()
        if notes:
            ABCDElement(unit, 'Notes', text=notes)

    if validate:
        check(validate_xml(datasets), 'ABCD data not valid')

    return ElementTree(datasets)



class ABCDExporter(object):
    """
    Export Plants to an ABCD file.
    """

    def start(self, filename=None, plants=None):
        if filename == None: # no filename, ask the user
            d = gtk.FileChooserDialog(_("Choose a file to export to..."), None,
                                      gtk.FILE_CHOOSER_ACTION_SAVE,
                                      (gtk.STOCK_OK, gtk.RESPONSE_ACCEPT,
                                       gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL))
            response = d.run()
            filename = d.get_filename()
            d.destroy()
            if response != gtk.RESPONSE_ACCEPT or filename == None:
                return

        if plants:
            nplants = len(plants)
        else:
            nplants = db.Session().query(Plant).count()

        if nplants > 3000:
            msg = _('You are exporting %(nplants)s plants to ABCD format.  ' \
                    'Exporting this many plants may take several minutes.  '\
                    '\n\n<i>Would you like to continue?</i>') \
                    % ({'nplants': nplants})
            if not utils.yes_no_dialog(msg):
                return
        self.run(filename, plants)


    def run(self, filename, plants=None):
        if filename == None:
            raise ValueError("filename can not be None")

        if os.path.exists(filename) and not os.path.isfile(filename):
            raise ValueError("%s exists and is not a a regular file" \
                                 % filename)

        # if plants is None then export all plants, this could be huge
        # TODO: do something about this, like list the number of plants
        # to be returned and make sure this is what the user wants
        if plants == None:
            plants = db.Session().query(Plant).all()

        # TODO: move PlantABCDAdapter, AccessionABCDAdapter and
        # PlantABCDAdapter into the ABCD plugin
        from bauble.plugins.report.xsl import PlantABCDAdapter
        data = create_abcd([PlantABCDAdapter(p) for p in plants],
                           validate=False)

        data.write_c14n(filename)

        # validate after the file is written so we still have some
        # output but let the user know the file isn't valid ABCD
        if not validate_xml(data):
            msg = _("The ABCD file was created but failed to validate "
                    "correctly against the ABCD standard.")
            utils.message_dialog(msg, gtk.MESSAGE_WARNING)


class ABCDExportTool(pluginmgr.Tool):
    category = _("Export")
    label = _("ABCD")

    @classmethod
    def start(cls):
        ABCDExporter().start()


class ABCDImexPlugin(pluginmgr.Plugin):
    tools = [ABCDExportTool]
    depends = ["PlantsPlugin"]


try:
    import lxml.etree as etree
    import lxml._elementpath # put this here sp py2exe picks it up
    from lxml.etree import Element, SubElement, ElementTree
except ImportError:
    utils.message_dialog(_('The <i>lxml</i> package is required for the '
                           'ABCD plugin'))
else:
    plugin = ABCDImexPlugin
