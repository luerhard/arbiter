# Users and permissions

Administrators manage system deployment, user account creation, user group assignments, and Django permissions. Access the admin interface at `/admin` using administrator credentials.

## 1. Admin Homepage

Log in at `http://<your-server-ip>/admin`. The dashboard provides quick access to User and Group management, along with a log of recent administrative actions.

:::{figure} ../screenshots/admin.png
:width: 650px
:align: center
:alt: Django Admin Homepage

**Figure 20: Django Administration Homepage**. Central management portal for site administration, user accounts, and system logs.
:::

## 2. Add Users

To register new Annotators or Experts:

1. Under **Users**, click **+ Add**.
2. Enter a unique username and password.
3. Click **Save** to create the user account.

:::{figure} ../screenshots/admin_add_user.png
:width: 650px
:align: center
:alt: Add User Form

**Figure 21: User Registration Form**. Admin form for creating new user credentials.
:::

## 3. Allow Self-Registration

By default only administrators create accounts. To let people create their own:

1. Under **Core**, click **Site settings**.
2. Tick **Allow registration** and click **Save**.

The login page then links to a registration page. Accounts made there are ordinary users: like every user they can create projects and be added to others, but they cannot open the admin. Untick the box to close registration again; existing accounts stay.

## 4. Manage User Groups

Organize users into functional groups to streamline role assignments:

1. Navigate to **Groups** under Authentication and Authorization.
2. Use the dual-list selector to assign users to specific system groups (e.g., Annotators, Experts).

:::{figure} ../screenshots/admin_user_groups.png
:width: 650px
:align: center
:alt: User Group Assignment

**Figure 22: User Group Management**. Interface for assigning users to designated functional groups.
:::

## 5. Manage User Permissions

Fine-tune model-level access rights for specific accounts or groups:

1. Open a user account profile in the admin portal.
2. In the **User permissions** section, select specific Django model permissions (e.g., `Expert | codebook draft | Can add codebook draft`, `Projects | batch | Can add batch`).
3. Click **Save** to enforce permission settings.

:::{figure} ../screenshots/admin_user_permissions.png
:width: 650px
:align: center
:alt: User Permissions Selector

**Figure 23: Fine-Grained User Permissions**. Selector panel for assigning specific system and model permissions to user profiles.
:::
