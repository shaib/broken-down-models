from django import VERSION as DJANGO_VERSION
from django.contrib.auth import get_user_model
from django.test import TestCase, skipIfDBFeature, skipUnlessDBFeature

from .models import Child, UserChild, Nephew, TimeStampedChild, ChildProxy, ChildWithVirtualNonParent, ParentB

can_return_rows_from_bulk_insert = (
    'can_return_ids_from_bulk_insert'
    if DJANGO_VERSION < (3, 0) else
    'can_return_rows_from_bulk_insert'
)


# TODO: Rename test classes
class SelectRelatedTestCase(TestCase):

    ChildClass = Child

    def setUp(self):
        super().setUp()
        self.ChildClass.objects.create(para_name='A', parb_name='B', parc_name='C', child_name='Xerxes')

    def test_parents_not_joined_by_default(self):
        """
        By default, fetching a broken-down model selects only the child fields.
        Accessing parent fields requires further database queries.
        """
        with self.assertNumQueries(1):
            c = self.ChildClass.objects.get(child_name='Xerxes')
        with self.assertNumQueries(3):
            parents = [c.para_name, c.parb_name, c.parc_name]
        self.assertEqual("".join(parents), "ABC")

    def test_field_access_fetches_whole_parent(self):
        """
        When a parent field is accessed for the first time, all the
        fields from that parent (and only them) are fetched with it.
        """
        with self.assertNumQueries(2):
            c = self.ChildClass.objects.get(child_name='Xerxes')
            self.assertIs(c.para_zit, True)
        with self.assertNumQueries(0):
            self.assertEqual(c.para_name, 'A')
        with self.assertNumQueries(2):
            self.assertIs(c.parb_zit, True)
            self.assertIs(c.parc_zit, True)
        with self.assertNumQueries(0):
            parents = [c.para_name, c.parb_name, c.parc_name]
            self.assertEqual("".join(parents), "ABC")

    def test_select_related_single_direct(self):
        """select_related() with a single, immediate parent link, joins the parent to the selection"""
        with self.assertNumQueries(1):
            c = self.ChildClass.objects.select_related('parenta_ptr').get(child_name='Xerxes')
            self.assertEqual((c.para_zit, c.para_name), (True, 'A'))
        with self.assertNumQueries(1):
            self.assertIs(c.parb_zit, True)
        with self.assertNumQueries(1):
            self.assertEqual(c.parc_name, 'C')

    def test_select_related_all_direct(self):
        """select_related() with no arguments joins all the parents to the selection"""
        with self.assertNumQueries(1):
            c = self.ChildClass.objects.select_related().get(child_name='Xerxes')
            self.assertEqual((c.para_zit, c.para_name), (True, 'A'))
            self.assertIs(c.parb_zit, True)
            self.assertEqual(c.parc_name, 'C')

    def test_fetch_all_parents(self):
        """fetch_all_parents() joins all the parents to the selection"""
        with self.assertNumQueries(1):
            c = self.ChildClass.objects.fetch_all_parents().get(child_name='Xerxes')
            self.assertEqual((c.para_zit, c.para_name), (True, 'A'))
            self.assertIs(c.parb_zit, True)
            self.assertEqual(c.parc_name, 'C')

    def test_select_related_non_parent(self):
        user = get_user_model().objects.create(username='artaxerxes')
        c = self.ChildClass.objects.get(child_name='Xerxes')
        c.user = user
        c.save()
        with self.assertNumQueries(1):
            cc = self.ChildClass.objects.select_related('user').get(child_name='Xerxes')
            self.assertEqual(cc.user.username, 'artaxerxes')

    def test_delete_qset(self):
        # 5 queries -- one to get the objects, and one to delete each part
        with self.assertNumQueries(5):
            self.ChildClass.objects.filter(child_name='Xerxes').delete()

    def test_delete_many(self):
        self.ChildClass.objects.create(para_name='A', parb_name='B', parc_name='C', child_name='Yeryes')
        self.ChildClass.objects.create(para_name='A', parb_name='B', parc_name='C', child_name='Zerzes')
        # 5 queries -- one to get the objects, and one to delete each part
        with self.assertNumQueries(5):
            self.ChildClass.objects.filter(child_name='Xerxes').delete()

    def test_delete_object(self):
        obj = self.ChildClass.objects.get(child_name='Xerxes')
        # 5 queries -- one to fill out the object, and one to delete each part
        with self.assertNumQueries(5):
            obj.delete()

    def test_getattr_if_loaded_gets_loaded(self):
        obj = self.ChildClass.objects.get(child_name='Xerxes')
        with self.assertNumQueries(0):
            child_name = obj.getattr_if_loaded('child_name', 'Pericles')
            self.assertEqual(child_name, 'Xerxes')

    def test_getattr_if_loaded_no_query(self):
        obj = self.ChildClass.objects.get(child_name='Xerxes')
        with self.assertNumQueries(0):
            para_name = obj.getattr_if_loaded('para_name')
            self.assertIsNone(para_name)
            parb_name = obj.getattr_if_loaded('parb_name', 'Yudokolis')
            self.assertEqual(parb_name, 'Yudokolis')

    def test_getattr_if_loaded_warns_on_error(self):
        obj = self.ChildClass.objects.get(child_name='Xerxes')
        model_name = self.ChildClass._meta.label
        with self.assertNumQueries(0):
            with self.assertWarnsMessage(UserWarning, f"{model_name} instance has no attribute 'pneumonia'"):
                pneumonia = obj.getattr_if_loaded('pneumonia', ...)
                self.assertEqual(pneumonia, ...)

    def test_refresh_from_db_all_parents(self):
        c = self.ChildClass.objects.get(child_name='Xerxes')
        with self.assertNumQueries(1):
            c.refresh_from_db(all_parents=True)
            self.assertEqual((c.para_zit, c.para_name), (True, 'A'))
            self.assertIs(c.parb_zit, True)
            self.assertEqual(c.parc_name, 'C')


class AbstractBaseClassTestCase(SelectRelatedTestCase):

    ChildClass = TimeStampedChild

    def test_the_abstract_base_works(self):
        # Make sure the last_modified field changes. Note we cannot compare to created_on
        # because it has its value filled in separately, so it starts out different from
        # last_modified (each gets a separate `timezone.now()` call).
        c = self.ChildClass.objects.get(child_name='Xerxes')
        orig_last_modified = c.last_modified
        c.child_name = 'Cyrus'
        c.save()
        self.assertNotEqual(orig_last_modified, c.last_modified)


class ProxyChildClassTestCase(SelectRelatedTestCase):

    ChildClass = ChildProxy


class UserChildTestCase(TestCase):

    def setUp(self):
        super().setUp()
        user = get_user_model().objects.create(username='artaxerxes')
        UserChild.objects.create(para_name='A', parb_name='B', parc_name='C', child_name='Xerxes', user=user)

    def test_select_related_non_parent(self):
        with self.assertNumQueries(1):
            uc = UserChild.objects.select_related('user').get(child_name='Xerxes')
            self.assertEqual(uc.user.username, 'artaxerxes')
        with self.assertNumQueries(1):
            # Note: We can do this with UserChild, it doesn't work with Child because its
            # FK to User is nullable and the empty select_related() doesn't collect nullable FKs.
            uc = UserChild.objects.select_related().get(child_name='Xerxes')
            self.assertEqual(uc.user.username, 'artaxerxes')

    def test_fetch_parents_doesnt_join_non_parent(self):
        """fetch_all_parents() joins parents to the selection, check that it doesn't join others"""
        with self.assertNumQueries(2):
            # Note: We can do this with UserChild, it doesn't work with Child because its
            # FK to User is nullable and the empty select_related() doesn't collect nullable FKs.
            uc = UserChild.objects.fetch_all_parents().get(child_name='Xerxes')
            self.assertEqual(uc.user.username, 'artaxerxes')

    def test_refresh_from_db_all_parents_doesnt_join_non_parent(self):
        uc = UserChild.objects.get(child_name='Xerxes')
        with self.assertNumQueries(2):
            uc.refresh_from_db(all_parents=True)
            self.assertEqual(uc.user.username, 'artaxerxes')


class ObjectCreationTestCase(TestCase):

    def test_create_child_with_id(self):
        """Verify the pk is not overwritten with None or anything else during object creation"""
        u = Child(id=12, para_name='A', parb_name='B', parc_name='C', child_name='Xerxes')
        self.assertEqual(u.id, 12)


class UncleTestCase(TestCase):
    def test_select_related_through_parent(self):
        user = get_user_model().objects.create(username='artaxerxes')
        child = Nephew.objects.create(parfk_user=user)
        with self.assertNumQueries(1):
            c = Nephew.objects.select_related('parfk_user').get(pk=child.pk)
            self.assertEqual(c.parfk_user.username, 'artaxerxes')

    def test_select_related_through_parent_with_id(self):
        """
        select-related through a parent had a subtle failure: it brought the related object and set
        the FK field to it, but it didn't set the related *_id field. Consequently, if the id field
        was accessed directly, it was fetched -- and in fact, even threw away the already-fetched
        related object. Thus, the assertEqual() line below, which we expected to perform no queries,
        actually performed two -- one to get the parfk_user_id field, and then one to get
        the parfk_user object.
        Now, it sets everything properly
        """
        user = get_user_model().objects.create(username='artaxerxes')
        child = Nephew.objects.create(parfk_user=user)
        with self.assertNumQueries(1):
            c = Nephew.objects.select_related('parfk_user').get(pk=child.pk)
            self.assertEqual(c.parfk_user_id, c.parfk_user.id)


class VirtualNonParentTestCase(TestCase):

    ChildClass = ChildWithVirtualNonParent

    def setUp(self):
        super().setUp()
        self.child = self.ChildClass.objects.create(para_name='A', child_name='Xerxes')
        # ParentB serves as the virtually-connected non-parent
        ParentB.objects.create(bid=self.child.id, parb_name="Ferb")

    def test_parents_not_joined_by_default(self):
        """
        By default, fetching a broken-down model selects only the child fields.
        Accessing parent fields requires further database queries.
        """
        with self.assertNumQueries(1):
            c = self.ChildClass.objects.get(child_name='Xerxes')
        with self.assertNumQueries(2):
            parents = [c.para_name, c.b.parb_name]
        self.assertEqual("".join(parents), "AFerb")

    def test_select_related_parent(self):
        """select_related() with a single, immediate parent link, joins the parent to the selection"""
        with self.assertNumQueries(1):
            c = self.ChildClass.objects.select_related('parenta_ptr').get(child_name='Xerxes')
            self.assertEqual((c.para_zit, c.para_name), (True, 'A'))
        with self.assertNumQueries(1):
            self.assertIs(c.b.parb_zit, True)

    def test_select_related_non_parent(self):
        with self.assertNumQueries(1):
            c = self.ChildClass.objects.select_related('b').get(child_name='Xerxes')
            self.assertIs(c.b.parb_zit, True)
        with self.assertNumQueries(1):
            self.assertEqual((c.para_zit, c.para_name), (True, 'A'))

    def test_select_related_all(self):
        """select_related() with no arguments joins all the parents to the selection"""
        with self.assertNumQueries(1):
            c = self.ChildClass.objects.select_related().get(child_name='Xerxes')
            self.assertEqual((c.para_zit, c.para_name), (True, 'A'))
            self.assertIs(c.b.parb_zit, True)


class ObjectUpdateTestCase(TestCase):

    def setUp(self) -> None:
        self.child = Child.objects.create(id=12, para_name='A', parb_name='B', parc_name='C', parc_zit=True, child_name='Xerxes')

    def test_update_parent_field(self):
        c = Child.objects.get(id=12)
        c.child_name = "Cyrus"
        c.parc_zit = False
        c.save()
        # Get a fresh copy
        c = Child.objects.get(id=12)
        self.assertFalse(c.parc_zit)

    def test_update_parent_field_with_other_parent_field_access(self):
        c = Child.objects.get(id=12)
        c.parc_zit = False
        self.assertFalse(c.parc_zit)
        self.assertEqual(c.parc_name, 'C')  # Reading parc_name may reset parc_zit
        self.assertFalse(c.parc_zit)
        c.save()
        # Get a fresh copy
        c = Child.objects.get(id=12)
        self.assertFalse(c.parc_zit)


class BulkCreateTestCase(TestCase):

    @skipIfDBFeature(can_return_rows_from_bulk_insert)
    def test_unsupported_backend(self):
        children = [
            Child(para_name='A0', parb_name='B0', parc_name='C0', parc_zit=True, child_name='X0'),
            Child(para_name='A1', parb_name='B1', parc_name='C1', parc_zit=True, child_name='X1'),
            Child(para_name='A2', parb_name='B2', parc_name='C2', parc_zit=True, child_name='X2'),
        ]
        with self.assertRaisesMessage(ValueError, 'bulk_create for broken-down models requires that PKs be set'):
            Child.objects.bulk_create(children)

    @skipUnlessDBFeature(can_return_rows_from_bulk_insert)
    def test_supported_backend(self):
        children = [
            Child(para_name='A0', parb_name='B0', parc_name='C0', parc_zit=True, child_name='X0'),
            Child(para_name='A1', parb_name='B1', parc_name='C1', parc_zit=True, child_name='X1'),
            Child(para_name='A2', parb_name='B2', parc_name='C2', parc_zit=True, child_name='X2'),
        ]
        Child.objects.bulk_create(children)
        kids = Child.objects.filter(child_name__in=['X0', 'X1', 'X2'])
        self.assertEqual(len(kids), 3)
        with self.assertNumQueries(3):
            for kid in kids:
                self.assertIs(kid.parc_zit, True)

    def test_provided_ids(self):
        """This should work whether or not the backend can return rows/ids from bulk insert"""
        children = [
            Child(id=22, para_name='A0', parb_name='B0', parc_name='C0', parc_zit=True, child_name='X0'),
            Child(id=23, para_name='A1', parb_name='B1', parc_name='C1', parc_zit=True, child_name='X1'),
            Child(id=24, para_name='A2', parb_name='B2', parc_name='C2', parc_zit=True, child_name='X2'),
        ]
        Child.objects.bulk_create(children)
        kids = Child.objects.filter(child_name__in=['X0', 'X1', 'X2'])
        self.assertEqual(len(kids), 3)
        with self.assertNumQueries(3):
            for kid in kids:
                self.assertIs(kid.parc_zit, True)
