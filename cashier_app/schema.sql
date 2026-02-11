CREATE EXTENSION IF NOT EXISTS pgcrypto; -- pro gen_random_uuid()
-- CREATE EXTENSION IF NOT EXISTS citext; -- case-insensitive text


-- // metadata / reference_id / notes
-- // Add indexes on tag_id, account_id, and time like columns. Consider partitioning transactions by time if volume is very high.
-- // Consider row-level security/audit logging if needed.

-- make sure all the trigger constraints work (in tests?)

-- make soft deletes cascade on other deletes/soft deletes?

-- add logs tables (maybe not tables, outside db)

-- allow negative balances here, but forbid them in the backend code

-- add wallet expiration after some time if there is no owner



-- -- enum for clarity (optional)
-- CREATE TYPE account_type AS ENUM ('user','employee');

-- CREATE TABLE accounts (
--   id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
--   account_type  account_type NOT NULL,
--   username      text NOT NULL,
--   email         citext NOT NULL,
--   password_hash text NOT NULL,
--   created_at    timestamptz NOT NULL DEFAULT now(),
--   deleted_at    timestamptz
-- );

-- -- Unique constraints: choose global uniqueness or per-type.
-- -- Global:
-- CREATE UNIQUE INDEX unique_accounts_username_active ON accounts (LOWER(username)) WHERE deleted_at IS NULL;
-- CREATE UNIQUE INDEX unique_accounts_email_active ON accounts (email) WHERE deleted_at IS NULL;

-- -- If you prefer per-type uniqueness:
-- -- CREATE UNIQUE INDEX unique_accounts_username_per_type_active ON accounts (account_type, LOWER(username)) WHERE deleted_at IS NULL;
-- Employee-specific table:

-- sql
-- Copy code
-- CREATE TABLE employee_profiles (
--   account_id   uuid PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
--   is_admin     boolean NOT NULL DEFAULT FALSE,
--   created_by   uuid REFERENCES accounts(id), -- should reference an employee account
--   created_at   timestamptz NOT NULL DEFAULT now()
-- );
-- -- optionally add CHECK to ensure associated account is employee
-- ALTER TABLE employee_profiles
--   ADD CONSTRAINT employee_profiles_only_for_employees
--   CHECK (
--     (SELECT account_type FROM accounts WHERE accounts.id = employee_profiles.account_id) = 'employee'
--   );



-- ======================== employees ========================
CREATE TABLE IF NOT EXISTS employees (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  username        text NOT NULL,
  email           text NOT NULL, -- add verification
  password_hash   text NOT NULL, -- Argon2 hash string (contains salt)
  is_admin        boolean NOT NULL DEFAULT FALSE,
  created_by      uuid REFERENCES employees(id) ON DELETE RESTRICT,
  created_at      timestamptz NOT NULL DEFAULT now(),
  deleted_at      timestamptz -- NULL -> existuje, NOT NULL -> smazáno
);
CREATE UNIQUE INDEX IF NOT EXISTS unique_index_employees_username_active ON employees (LOWER(username)) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS unique_index_employees_email_active ON employees (email) WHERE deleted_at IS NULL;

-- blokuje delete a změnu created_at, created_by:
-- u insert/update odstraní mezery na začátku a konci pro email/username a u email dá všchno malým
CREATE OR REPLACE FUNCTION employees_block_delete_limit_update_insert()
RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'UPDATE' THEN
    IF (NEW.created_at IS DISTINCT FROM OLD.created_at) THEN
      RAISE EXCEPTION 'created_at is immutable and cannot be changed';
    END IF;
    IF (NEW.created_by IS DISTINCT FROM OLD.created_by) THEN
      RAISE EXCEPTION 'created_by is immutable and cannot be changed';
    END IF;
  ELSIF TG_OP = 'DELETE' THEN -- Soft-delete
    IF OLD.deleted_at IS NULL THEN
      UPDATE employees
      SET deleted_at = now()
      WHERE id = OLD.id AND deleted_at IS NULL;
      RETURN NULL; -- zastav DELETE
    ELSE
      RETURN NULL;
    END IF;
  END IF;

  IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
    NEW.username := trim(NEW.username);
    NEW.email := lower(trim(NEW.email));
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_employees_block_delete_limit_update_insert
  BEFORE UPDATE OR DELETE OR INSERT ON employees
  FOR EACH ROW
  EXECUTE FUNCTION employees_block_delete_limit_update_insert();



-- ======================== users ========================
CREATE TABLE IF NOT EXISTS users (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  first_name        text NOT NULL,
  last_name         text NOT NULL,
  email             text, -- add verification
  phone_number      text, -- +[country code][number] (CZ: +420123456789) E.164 format
  other_identifier  text,
  created_at        timestamptz NOT NULL DEFAULT now(),
  deleted_at        timestamptz, -- NULL -> existuje, NOT NULL -> smazáno
  CONSTRAINT valid_phone_number_check
    CHECK (phone_number ~ '^\+[1-9]\d{0,14}$')
);
CREATE UNIQUE INDEX unique_index_users_names_email_phone_identifier
  ON users (
    lower(first_name),
    lower(last_name),
    COALESCE(NULLIF(lower(email), ''), '<<__NULL___2025__>>'),
    COALESCE(NULLIF(phone_number, ''), '<<__NULL___2025__>>'),
    COALESCE(NULLIF(lower(other_identifier), ''), '<<__NULL___2025__>>')
  )
  WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS unique_index_users_email_active ON users (email) WHERE deleted_at IS NULL;

-- blokuje delete a změnu created_at:
-- u insert/update:
  -- odstraní mezery na začátku a konci pro email/first_name/last_name/phone_number/other_identifier
  -- email dá všechno malým
  -- first_name a last_name dá první písmeno velké a zbytek malé
  -- kontroluje že aspoň jedno z email, phone_number a other_identifier je vyplněné

  -- při nastavení deleted_at smaže wallets uživatele
CREATE OR REPLACE FUNCTION users_block_delete_limit_update_insert()
RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'UPDATE' THEN
    IF (NEW.created_at IS DISTINCT FROM OLD.created_at) THEN
      RAISE EXCEPTION 'created_at is immutable and cannot be changed';
    END IF;

    IF OLD.deleted_at IS NULL AND NEW.deleted_at IS NOT NULL THEN
      UPDATE wallets
      SET deleted_at = COALESCE(NEW.deleted_at, now())
      WHERE owner_id = NEW.id
        AND deleted_at IS NULL;
    END IF;

  ELSIF TG_OP = 'DELETE' THEN -- Soft-delete
    IF OLD.deleted_at IS NULL THEN
      UPDATE users
      SET deleted_at = now()
      WHERE id = OLD.id AND deleted_at IS NULL;

      UPDATE wallets
      SET deleted_at = now()
      WHERE owner_id = OLD.id
        AND deleted_at IS NULL;
        
      RETURN NULL; -- zastav DELETE
    ELSE
      RETURN NULL;
    END IF;
  END IF;

  IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
    NEW.first_name := initcap(trim(NEW.first_name));
    NEW.last_name := initcap(trim(NEW.last_name));
    NEW.email := lower(trim(NEW.email));
    NEW.phone_number := trim(NEW.phone_number);
    NEW.other_identifier := trim(NEW.other_identifier);

    IF (NEW.email IS NULL AND NEW.phone_number IS NULL AND NEW.other_identifier IS NULL) THEN
      RAISE EXCEPTION 'at least one of email, phone_number, other_identifier have to be set';
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_users_block_delete_limit_update_insert
  BEFORE UPDATE OR DELETE OR INSERT ON users
  FOR EACH ROW
  EXECUTE FUNCTION users_block_delete_limit_update_insert();



-- currently only for employees
CREATE TABLE IF NOT EXISTS sessions (
  id            text PRIMARY KEY,        -- opaque session id
  data          jsonb NOT NULL,          -- session data
  employee_id   uuid REFERENCES employees(id) ON DELETE CASCADE,
  ip            text,
  ua_hash       text,
  created_at    timestamptz NOT NULL DEFAULT now(),
  modified_at   timestamptz NOT NULL DEFAULT now(),
  expires_at    timestamptz
);
-- CREATE INDEX IF NOT EXISTS sessions_expires_idx ON sessions (expires_at);


CREATE OR REPLACE FUNCTION sessions_update_modified_at()
RETURNS trigger AS $$
BEGIN
  NEW.modified_at := now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sessions_update_modified_at
  BEFORE UPDATE ON sessions
  FOR EACH ROW
  EXECUTE FUNCTION sessions_update_modified_at();



-- ======================== events ========================
CREATE TABLE IF NOT EXISTS events (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name        text NOT NULL,
  start_at    timestamptz,
  end_at      timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now(),
  created_by  uuid NOT NULL REFERENCES employees(id) ON DELETE RESTRICT,
  deleted_at timestamptz,
  CONSTRAINT events_start_at_before_end_at_check
    CHECK (start_at IS NULL OR end_at IS NULL OR start_at <= end_at)
  -- deletion? (through deleted_at or actually delete it and all (or some) related stuff but make sure there is a big warning or no deletion allowed)
  -- or only allow deletion for events with nothing import referencing it or stuff that references it
);
CREATE UNIQUE INDEX IF NOT EXISTS unique_index_events_name_active ON events (LOWER(name)) WHERE deleted_at IS NULL;

              -- (odendáno: zajistí že end_at jde pouze nastavit po now())
-- blokuje delete a změnu created_at, created_by
-- odendá mezery na začátku a konci u name
CREATE OR REPLACE FUNCTION events_block_delete_limit_update_insert()
RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'UPDATE' THEN
    IF (NEW.created_at IS DISTINCT FROM OLD.created_at) THEN
      RAISE EXCEPTION 'created_at is immutable and cannot be changed';
    END IF;
    IF (NEW.created_by IS DISTINCT FROM OLD.created_by) THEN
      RAISE EXCEPTION 'created_by is immutable and cannot be changed';
    END IF;

  ELSIF TG_OP = 'DELETE' THEN -- Soft-delete
    IF OLD.deleted_at IS NULL THEN
      UPDATE events
      SET deleted_at = now()
      WHERE id = OLD.id AND deleted_at IS NULL;
      RETURN NULL; -- zastav DELETE
    ELSE
      RETURN NULL;
    END IF;
  END IF;

  IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
    -- IF NEW.end_at <= now() THEN
    --   RAISE EXCEPTION 'end_at can not be set to before now()';
    -- END IF;

    NEW.name := TRIM(New.name);
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_events_block_delete_limit_update_insert
  BEFORE UPDATE OR DELETE OR INSERT ON events
  FOR EACH ROW
  EXECUTE FUNCTION events_block_delete_limit_update_insert();



-- ======================== booths ========================
CREATE TABLE IF NOT EXISTS booths (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name            text NOT NULL,
  event_id        uuid NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
  booth_type      text NOT NULL,
  created_at      timestamptz NOT NULL DEFAULT now(),
  created_by      uuid NOT NULL REFERENCES employees(id) ON DELETE RESTRICT,
  deleted_at      timestamptz,
  CONSTRAINT booth_type_check
    CHECK (booth_type IN ('cashier', 'seller'))
);
CREATE UNIQUE INDEX IF NOT EXISTS unique_index_booths_event_id_name_active ON booths (event_id, LOWER(name)) WHERE deleted_at IS NULL;

-- odendá mezery ze začátku a konce name
-- blokuje delete a změnu event_id, booth_type, created_at, created_by:
CREATE OR REPLACE FUNCTION booths_block_delete_limit_update_insert()
RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'UPDATE' OR TG_OP = 'INSERT' THEN
    NEW.name := TRIM(NEW.name);
  END IF;

  IF TG_OP = 'UPDATE' THEN
    IF (NEW.created_at IS DISTINCT FROM OLD.created_at) THEN
      RAISE EXCEPTION 'created_at is immutable and cannot be changed';
    END IF;
    IF (NEW.created_by IS DISTINCT FROM OLD.created_by) THEN
      RAISE EXCEPTION 'created_by is immutable and cannot be changed';
    END IF;
    IF (NEW.event_id IS DISTINCT FROM OLD.event_id) THEN
      RAISE EXCEPTION 'event_id is immutable and cannot be changed';
    END IF;
    IF (NEW.booth_type IS DISTINCT FROM OLD.booth_type) THEN
      RAISE EXCEPTION 'booth_type is immutable and cannot be changed';
    END IF;
    -- IF (OLD.deleted_at IS NOT NULL AND NEW.deleted_at IS DISTINCT FROM OLD.deleted_at) THEN
    --   RAISE EXCEPTION 'can not change deleted_at after deletion';
    -- END IF;

  ELSIF TG_OP = 'DELETE' THEN -- Soft-delete
    IF OLD.deleted_at IS NULL THEN
      UPDATE booths
      SET deleted_at = now()
      WHERE id = OLD.id AND deleted_at IS NULL;
      RETURN NULL; -- zastav DELETE
    ELSE
      RETURN NULL;
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_booths_block_delete_limit_update_insert
  BEFORE INSERT OR UPDATE OR DELETE ON booths
  FOR EACH ROW
  EXECUTE FUNCTION booths_block_delete_limit_update_insert();



-- ======================== product_images ========================
CREATE TABLE IF NOT EXISTS product_images (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  image_path          text NOT NULL, -- obsahuje celý path i s filename
  image_filename      text,
  image_mime_type     text, 
  image_size_bytes    int,
  image_width         int,
  image_height        int,
  -- image_alt_text      text,
  CONSTRAINT image_mime_type_check
    CHECK (image_mime_type IN ('image/jpeg', 'image/png', 'image/webp'))
);

-- <img alt="..." src="/static/uploads/products/uid_thumb.jpg"
--      srcset="/static/uploads/products/uid_small.jpg 300w,
--              /static/uploads/products/uid_medium.jpg 800w,
--              /static/uploads/products/uid_large.jpg 1200w"
--      sizes="(max-width:600px) 300px, (max-width:1200px) 800px, 1200px" loading="lazy">



-- ======================== product_images ========================
CREATE TABLE IF NOT EXISTS product_images_failed_to_delete (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  image_path          text NOT NULL, -- obsahuje celý path i s filename
  attempt             int NOT NULL DEFAULT 0
);



-- ======================== products ========================
-- transakce se sem neodkazují, protože se řádky mohou jakkoliv měnit
-- potřebné hodnoty se pouze zkopírují
CREATE TABLE IF NOT EXISTS products (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id      uuid NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
  name          text NOT NULL,
  price         int NOT NULL, -- může být záporná
  image_id      uuid REFERENCES product_images(id) ON DELETE SET NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  deleted_at    timestamptz
  -- CONSTRAINT price_is_positive_check
  --   CHECK (price >= 0)
);
CREATE UNIQUE INDEX IF NOT EXISTS unique_index_products_event_id_name_active ON products (event_id, LOWER(name)) WHERE deleted_at IS NULL;


-- odendá mezery na začátku a konci u name
-- blokuje delete
CREATE OR REPLACE FUNCTION products_block_delete_edit_insert_update()
RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
    NEW.name := TRIM(New.name);
  END IF;

  IF TG_OP = 'DELETE' THEN -- Soft-delete
    IF OLD.deleted_at IS NULL THEN
      UPDATE products
      SET deleted_at = now()
      WHERE id = OLD.id AND deleted_at IS NULL;
      RETURN NULL; -- zastav DELETE
    ELSE
      RETURN NULL;
    END IF;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_products_block_delete_edit_insert_update
  BEFORE UPDATE OR INSERT OR DELETE ON products
  FOR EACH ROW
  EXECUTE FUNCTION products_block_delete_edit_insert_update();



-- ======================== product_booth_link ========================
CREATE TABLE IF NOT EXISTS product_booth_link (
  product_id  uuid NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  booth_id    uuid NOT NULL REFERENCES booths(id) ON DELETE CASCADE,
  PRIMARY KEY (product_id, booth_id)
);

-- zkontroluje jestli se product event_id a booth event_id shodují
-- zkontroluje, že booth a product existují
-- kontroluje že booth je seller
CREATE OR REPLACE FUNCTION product_booth_link_limit_update_insert()
RETURNS trigger AS $$
DECLARE
  booth_event_id uuid;
  product_event_id uuid;
  found_row int;
BEGIN
  IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
    SELECT event_id INTO booth_event_id
      FROM booths
      WHERE NEW.booth_id = id
      AND booth_type = 'seller'
      AND deleted_at IS NULL;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'booth % does not exist, is not a seller or is deleted', NEW.booth_id;
    END IF;

    SELECT 1 INTO found_row
      FROM products
      WHERE NEW.product_id = id
      AND deleted_at IS NULL;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'product % does not exist', NEW.product_id;
    END IF;

    SELECT event_id INTO product_event_id
      FROM products
      WHERE NEW.product_id = id;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'product % does not exist', NEW.product_id;
    END IF;

    IF booth_event_id IS DISTINCT FROM product_event_id THEN
      RAISE EXCEPTION 'booths event_id % and product event_id % do not match', booth_event_id, product_event_id;
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_product_booth_link_limit_update_insert
  BEFORE INSERT OR UPDATE ON product_booth_link
  FOR EACH ROW
  EXECUTE FUNCTION product_booth_link_limit_update_insert();



-- ======================== categories ========================
CREATE TABLE IF NOT EXISTS categories (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name       text NOT NULL,
  event_id   uuid NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
  deleted_at timestamptz
);
CREATE UNIQUE INDEX IF NOT EXISTS unique_index_categories_event_id_name_active ON categories (event_id, LOWER(name)) WHERE deleted_at IS NULL;


-- u insert/update odendává extra mezery ze začátku a konce
-- blokuje delete
CREATE OR REPLACE FUNCTION categories_block_delete_edit_update_insert()
RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
    NEW.name := trim(NEW.name);
  END IF;

  IF TG_OP = 'DELETE' THEN -- Soft-delete
    IF OLD.deleted_at IS NULL THEN
      UPDATE categories
      SET deleted_at = now()
      WHERE id = OLD.id AND deleted_at IS NULL;
      RETURN NULL; -- zastav DELETE
    ELSE
      RETURN NULL;
    END IF;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_categories_block_delete_edit_update_insert
  BEFORE UPDATE OR INSERT OR DELETE ON categories
  FOR EACH ROW
  EXECUTE FUNCTION categories_block_delete_edit_update_insert();



-- ======================== category_booth_link ========================
CREATE TABLE IF NOT EXISTS category_booth_link (
  category_id  uuid NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
  booth_id                uuid NOT NULL REFERENCES booths(id) ON DELETE CASCADE,
  PRIMARY KEY (category_id, booth_id)
);


-- u insert/update kontroluje: 
--   - jestli je event stejný u categories i booth a booth existuje
--   - zkontroluje, že booth a category existuje
--   - kontroluje že booth je seller
CREATE OR REPLACE FUNCTION category_booth_link_limit_insert_update()
RETURNS trigger AS $$
DECLARE
  category_event_id uuid;
  booth_event_id uuid;
  found_row int;
BEGIN
  IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
    SELECT event_id INTO booth_event_id
    FROM booths
    WHERE id = NEW.booth_id
    AND booth_type = 'seller'
    AND deleted_at IS NULL;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'booth % does not exist, is not a seller or is deleted', NEW.booth_id;
    END IF;

    SELECT 1 INTO found_row
    FROM categories
    WHERE id = NEW.category_id
    AND deleted_at IS NULL;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'category % does not exist', NEW.category_id;
    END IF;

    SELECT event_id INTO category_event_id
    FROM categories
    WHERE id = NEW.category_id;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'category % does not exist', NEW.category_id;
    END IF;

    IF category_event_id IS DISTINCT FROM booth_event_id THEN
      RAISE EXCEPTION 'booths event_id % and category event_id % do not match', booth_event_id, category_event_id;
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_category_booth_link_limit_insert_update
  BEFORE INSERT OR UPDATE ON category_booth_link
  FOR EACH ROW
  EXECUTE FUNCTION category_booth_link_limit_insert_update();



-- ======================== category_product_link ========================
CREATE TABLE IF NOT EXISTS category_product_link (
  category_id  uuid NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
  product_id              uuid REFERENCES products(id) ON DELETE CASCADE,
  PRIMARY KEY (category_id, product_id)
);


-- u insert/update kontroluje: 
--   - jestli je event stejný u categories i products
--   - jestli category a product existují
CREATE OR REPLACE FUNCTION category_product_link_limit_insert_update()
RETURNS trigger AS $$
DECLARE
  category_event_id uuid;
  product_event_id uuid;
BEGIN
  IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
    SELECT event_id INTO product_event_id
    FROM products
    WHERE id = NEW.product_id
    AND deleted_at IS NULL;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'product % does not exist', NEW.product_id;
    END IF;

    SELECT event_id INTO category_event_id
    FROM categories
    WHERE id = NEW.category_id
    AND deleted_at IS NULL;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'category % does not exist', NEW.category_id;
    END IF;

    IF category_event_id IS DISTINCT FROM product_event_id THEN
      RAISE EXCEPTION 'products event_id % and category event_id % do not match', product_event_id, category_event_id;
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_category_product_link_limit_insert_update
  BEFORE INSERT OR UPDATE ON category_product_link
  FOR EACH ROW
  EXECUTE FUNCTION category_product_link_limit_insert_update();



-- ======================== employee_event_booth_roles ========================
-- seller: může dělat payments
-- cashier: může dělat withdrawals and deposits
-- event_manager: může dělat cokoliv v akci (např dávat účtům roli cashier)
-- admin: (není částí této tabulky) může věci mimo akce (např. vytvářet účty)
CREATE TABLE IF NOT EXISTS employee_event_booth_roles (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id   uuid NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  event_id      uuid NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  booth_id      uuid REFERENCES booths(id) ON DELETE CASCADE, -- null -> event_manager
  role          text NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT role_check
    CHECK (role IN ('event_manager','cashier','seller'))
);
-- v této tabulce jsou delete i update povoleny
CREATE UNIQUE INDEX IF NOT EXISTS unique_index_employee_event_manager
ON employee_event_booth_roles(employee_id, event_id)
WHERE booth_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS unique_index_employee_booth
ON employee_event_booth_roles(employee_id, event_id, booth_id)
WHERE booth_id IS NOT NULL;


-- u insert/update kontroluje: 
--   - jestli je role null, tak ji automaticky doplní
--   - jestli je event stejný tady i booth a booth existuje (pokud booth_id není null)
--   - jestli se booths.booth_type a role shodují (pokud role není null)
--   - zajistí, že pokud je employee pro event event_manager, tak nemůže být přirazen k specifickému stánku
--   - zkontroluje jestli employee existuje
--(   - zajistí, že zde nemůže být přiřazen admin) už ne
CREATE OR REPLACE FUNCTION employee_event_booth_roles_limit_autocomplete_insert_update()
RETURNS trigger AS $$
DECLARE
  booth_event_id uuid;
  booths_type text;
  emp_is_admin boolean;
  found_row int;
BEGIN
  IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
    IF NEW.role IS NULL AND NEW.booth_id IS NULL THEN
      NEW.role := 'event_manager';
    END IF;

    SELECT is_admin INTO emp_is_admin
    FROM employees
    WHERE id = NEW.employee_id
      AND deleted_at IS NULL;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'employee % does not exist or is deleted', NEW.employee_id;
    END IF;

    -- IF emp_is_admin THEN
    --   RAISE EXCEPTION 'admins cannot be assigned to employee_event_booth_roles (employee %)', NEW.employee_id;
    -- END IF;

    IF NEW.booth_id IS NOT NULL THEN
      SELECT event_id, booth_type INTO booth_event_id, booths_type
      FROM booths
      WHERE NEW.booth_id = id
      AND deleted_at IS NULL;

      IF NOT FOUND THEN
        RAISE EXCEPTION 'booth % does not exist or is deleted', NEW.booth_id;
      END IF;

      IF NEW.role IS NULL THEN
        NEW.role := booths_type;
      END IF;

      IF booth_event_id IS DISTINCT FROM NEW.event_id THEN
        RAISE EXCEPTION 'booths event_id % and event_id % do not match', booth_event_id, NEW.event_id;
      END IF;

      IF booths_type IS DISTINCT FROM NEW.role THEN
        RAISE EXCEPTION 'booth_type % and role % do not match', booths_type, NEW.role;
      END IF;

      IF TG_OP = 'INSERT' THEN
        SELECT 1 INTO found_row
        FROM employee_event_booth_roles
        WHERE employee_id = NEW.employee_id
          AND event_id = NEW.event_id
          AND booth_id IS NULL
        LIMIT 1;
      ELSIF TG_OP = 'UPDATE' THEN
        SELECT 1 INTO found_row
        FROM employee_event_booth_roles
        WHERE employee_id = NEW.employee_id
          AND event_id = NEW.event_id
          AND booth_id IS NULL
          AND id IS DISTINCT FROM NEW.id
        LIMIT 1;
      END IF;

      IF FOUND THEN
        RAISE EXCEPTION 'employee % is already event_manager for event % and cannot be assigned to booths', NEW.employee_id, NEW.event_id;
      END IF;

    ELSIF NEW.booth_id IS NULL THEN
      IF NEW.role IS DISTINCT FROM 'event_manager' THEN
        RAISE EXCEPTION 'role must be event_manager when booth_id is NULL';
      END IF;

      IF TG_OP = 'INSERT' THEN
        SELECT 1 INTO found_row
        FROM employee_event_booth_roles
        WHERE employee_id = NEW.employee_id
          AND event_id = NEW.event_id
          AND booth_id IS NOT NULL
        LIMIT 1;
      ELSIF TG_OP = 'UPDATE' THEN
        SELECT 1 INTO found_row
        FROM employee_event_booth_roles
        WHERE employee_id = NEW.employee_id
          AND event_id = NEW.event_id
          AND booth_id IS NOT NULL
          AND id IS DISTINCT FROM NEW.id
        LIMIT 1;
      END IF;

      IF FOUND THEN
        RAISE EXCEPTION 'cannot assign event_manager for employee % on event % while they are assigned to booths', NEW.employee_id, NEW.event_id;
      END IF;

    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_employee_event_booth_roles_limit_autocomplete_insert_update
  BEFORE INSERT OR UPDATE ON employee_event_booth_roles
  FOR EACH ROW
  EXECUTE FUNCTION employee_event_booth_roles_limit_autocomplete_insert_update();



-- -- ======================== tags ========================
-- CREATE TABLE IF NOT EXISTS tags (
--   id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
--   is_being_used   boolean NOT NULL
-- );



-- ======================== wallets ========================
-- created by?
CREATE TABLE IF NOT EXISTS wallets (
  id                            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id                      uuid NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
  -- tag_id                        uuid REFERENCES tags(id) ON DELETE SET NULL,
  tag_id                        text NOT NULL,
  owner_id                      uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  balance_czk                   int NOT NULL DEFAULT 0, -- cache, není zdroj pravdy
  created_by                    uuid NOT NULL REFERENCES employees(id) ON DELETE RESTRICT,
  created_at                    timestamptz NOT NULL DEFAULT now(),
  deleted_at                    timestamptz
);
CREATE UNIQUE INDEX IF NOT EXISTS unique_index_event_tag_id_active ON wallets (event_id, tag_id) WHERE deleted_at IS NULL;
-- CREATE UNIQUE INDEX IF NOT EXISTS unique_index_owner_id_active ON wallets (owner_id) WHERE deleted_at IS NULL;

-- blokuje delete a změnu created_at
CREATE OR REPLACE FUNCTION wallets_block_delete_limit_update()
RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'UPDATE' THEN
    IF (NEW.created_at IS DISTINCT FROM OLD.created_at) THEN
      RAISE EXCEPTION 'created_at is immutable and cannot be changed';
    END IF;
    -- IF (OLD.deleted_at IS NOT NULL AND NEW.deleted_at IS DISTINCT FROM OLD.deleted_at) THEN
    --   RAISE EXCEPTION 'can not change deleted_at after deletion';
    -- END IF;

  ELSIF TG_OP = 'DELETE' THEN -- Soft-delete
    IF OLD.deleted_at IS NULL THEN
      UPDATE wallets
      SET deleted_at = now()
      WHERE id = OLD.id AND deleted_at IS NULL;
      RETURN NULL; -- zastav DELETE
    ELSE
      RETURN NULL;
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_wallets_block_delete_limit_update
  BEFORE UPDATE OR DELETE ON wallets
  FOR EACH ROW
  EXECUTE FUNCTION wallets_block_delete_limit_update();



-- ======================== transactions ========================
-- zdroj pravdy pro wallets, nedá se měnit
CREATE TABLE IF NOT EXISTS transactions (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  -- tag_id            uuid NOT NULL REFERENCES tags(id) ON DELETE RESTRICT,
  tag_id            text NOT NULL,
  wallet_id         uuid NOT NULL REFERENCES wallets(id) ON DELETE RESTRICT,
  user_id           uuid REFERENCES users(id) ON DELETE RESTRICT,
  event_id          uuid NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
  booth_id          uuid NOT NULL REFERENCES booths(id) ON DELETE RESTRICT,
  transaction_type  text NOT NULL,
  amount_czk        int NOT NULL , -- kladné -> peníze přidány na wallet, záporné -> peníze odebrány z wallet
  balance_before    int NOT NULL, -- dělá trigger
  balance_after     int NOT NULL, -- dělá trigger
  occurred_at       timestamptz NOT NULL DEFAULT now(),
  performed_by      uuid NOT NULL REFERENCES employees(id) ON DELETE RESTRICT,
  products_info     jsonb DEFAULT '[]'::jsonb, -- id (nezapomeň, že product mohl být smazán/upraven), price, name, quantity 

  idempotency_key   text, -- make uuid?
  request_fingerprint text -- sha256 hex důležitých částí: tag_id, wallet_id, user_id, event_id, booth_id, transaction_type, amount_czk, performed_by, products_info
  -- metadata          jsonb DEFAULT '{}'::jsonb, -- keep?, info about product?
  -- CONSTRAINT transaction_type_matches_amount_czk_check
  --   CHECK (
  --     (transaction_type IN ('deposit', 'refund') AND amount_czk >= 0)
  --     OR (transaction_type IN ('payment','withdrawal') AND amount_czk <= 0)
  --   ),
  CONSTRAINT balance_after_matches_balance_before_and_amount_czk_check
    CHECK (balance_after = balance_before + amount_czk),
  CONSTRAINT transaction_type_check
    CHECK (transaction_type IN ('payment', 'balance-change', 'refund'))
);
-- add the refund stuff
CREATE UNIQUE INDEX IF NOT EXISTS unique_index_transactions_idempotency_key
  ON transactions (idempotency_key);

-- blokuje delete a update
-- u insert kontroluje: 
--  - že event je aktivní
--  - že booth existuje
--  - že booth a wallet event_id a event_id jsou shodné
--  - user existuje (pokud není null)
--  - jestli employee existuje a má dostatečnou roli (patří k booth nebo je manager nebo admin)
--  - jestli booth může dělat tuto transaction
--  - jestli wallet existuje
--  - wallet.tag_id a wallet.user_id patří k transaction
--  - jestli wallet má dost peněz
-- počítá a zapisuje balance_before a balance_after
-- updatuje wallet balance_czk
CREATE OR REPLACE FUNCTION transactions_block_delete_update_limit_insert()
RETURNS trigger AS $$
DECLARE
  bal_before int;
  bal_after int;
  employee_booth_role text;
  employee_is_admin boolean;
  booth_event_id uuid;
  booth_booth_type text;
  wallet_event_id uuid;
  wallet_tag_id text;
  wallet_owner_id uuid;
BEGIN
  IF TG_OP = 'UPDATE' THEN
    RAISE EXCEPTION 'Updates are not allowed on table transactions';
  ELSIF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'Deletes are not allowed on table transactions';

  ELSIF TG_OP = 'INSERT' THEN
    -- event je aktivní
    PERFORM 1
      FROM events
      WHERE id = NEW.event_id
      AND start_at IS NOT NULL
      AND start_at <= NEW.occurred_at
      AND (end_at IS NULL OR NEW.occurred_at < end_at);

    IF NOT FOUND THEN
      RAISE EXCEPTION 'event % is not active', NEW.event_id;
    END IF;

    -- booth existuje, event_id = booths.event_id:
    SELECT event_id, booth_type INTO booth_event_id, booth_booth_type
      FROM booths
      WHERE id = NEW.booth_id
      AND deleted_at IS NULL;

      IF NOT FOUND THEN
        RAISE EXCEPTION 'booth % does not exist or is deleted', NEW.booth_id;
      END IF;

      IF booth_event_id IS DISTINCT FROM NEW.event_id THEN
        RAISE EXCEPTION 'booths event_id % and event_id % do not match', booth_event_id, NEW.event_id;
      END IF;

    -- user existuje:
    IF NEW.user_id IS NOT NULL THEN
      PERFORM 1
        FROM users
        WHERE id = NEW.user_id
        AND deleted_at IS NULL;

      IF NOT FOUND THEN
        RAISE EXCEPTION 'user % does not exist or is deleted', NEW.user_id;
      END IF;
    END IF;

    -- employee existuje:
    SELECT is_admin INTO employee_is_admin
      FROM employees
      WHERE id = NEW.performed_by
      AND deleted_at IS NULL;
    
    IF NOT FOUND THEN
      RAISE EXCEPTION 'employee % does not exist or is deleted', NEW.performed_by;
    END IF;

    -- employee má dostatečnou roli:
    SELECT role INTO employee_booth_role
      FROM employee_event_booth_roles
      WHERE employee_id = NEW.performed_by
      AND event_id = NEW.event_id
      AND (booth_id = NEW.booth_id OR booth_id IS NULL)
      ORDER BY (booth_id IS NOT NULL) DESC
      LIMIT 1;
    
    IF NOT FOUND AND NOT employee_is_admin THEN
      RAISE EXCEPTION 'employee % does not have any role in the booth', NEW.performed_by;
    END IF;

    -- transaction_type je shodné s booth_id
    IF booth_booth_type = 'cashier' AND NEW.transaction_type != 'balance-change' THEN
      RAISE EXCEPTION 'invalid booth type % for transaction_type %', booth_booth_type, NEW.transaction_type;
    END IF;
    IF booth_booth_type = 'seller' AND NOT (NEW.transaction_type IN ('payment', 'refund')) THEN
      RAISE EXCEPTION 'invalid booth type % for transaction_type %', booth_booth_type, NEW.transaction_type;
    END IF;

    -- IF NEW.transaction_type IN ('deposit', 'withdrawal')
    --   AND NOT (employee_booth_role IN ('cashier', 'event_manager') OR employee_is_admin) THEN
    --     RAISE EXCEPTION 'employee with role % does not have necessary role to perform %', employee_booth_role, NEW.transaction_type;
    -- END IF;
    -- IF NEW.transaction_type IN ('payment', 'refund')
    --   AND NOT (employee_booth_role IN ('seller', 'cashier', 'event_manager') OR employee_is_admin) THEN
    --     RAISE EXCEPTION 'employee with role % does not have necessary role to perform %', employee_booth_role, NEW.transaction_type;
    -- END IF;

    -- -- transaction_type je shodné s amount_czk
    -- IF NEW.transaction_type in ('deposit', 'refund') AND NEW.amount_czk <= 0 THEN
    --   RAISE EXCEPTION '% amount must be > 0', NEW.transaction_type;
    -- ELSIF (NEW.transaction_type IN ('payment', 'withdrawal')) AND NEW.amount_czk >= 0 THEN
    --   RAISE EXCEPTION '% amount must be < 0', NEW.transaction_type;
    -- END IF;

    
    -- wallet existuje, získej potřebné data a zamkni řadu
    SELECT tag_id, owner_id, balance_czk, event_id INTO wallet_tag_id, wallet_owner_id, bal_before, wallet_event_id
      FROM wallets
      WHERE id = NEW.wallet_id
      AND deleted_at IS NULL
      FOR UPDATE;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'wallet % does not exist or is deleted', NEW.wallet_id;
    END IF;

    -- event_id wallet a event_id se shodují
    IF wallet_event_id IS DISTINCT FROM NEW.event_id THEN
        RAISE EXCEPTION 'wallet event_id % and event_id % do not match', wallet_event_id, NEW.event_id;
      END IF;

    -- wallet.tag_id a wallet.user_id patří k transaction
    IF wallet_tag_id IS DISTINCT FROM NEW.tag_id THEN
      RAISE EXCEPTION 'wallet tag_id % does not match transaction tag_id %', wallet_tag_id, NEW.tag_id;
    END IF;

    IF wallet_owner_id IS DISTINCT FROM NEW.user_id THEN
      RAISE EXCEPTION 'wallet owner_id % does not match transaction user_id %', wallet_owner_id, NEW.user_id;
    END IF;

    -- spočítá balance_before
    bal_after := bal_before + NEW.amount_czk;

    -- wallet má dost peněz
    IF bal_after < 0 THEN
      RAISE EXCEPTION 'insufficient balance in wallet % (would be %)', NEW.wallet_id, bal_after;
    END IF;

    -- zapisuje balance_before a balance_after
    NEW.balance_before := bal_before;
    NEW.balance_after  := bal_after;
    -- updatuje wallet balance_czk
    UPDATE wallets SET balance_czk = bal_after WHERE id = NEW.wallet_id;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_transactions_block_delete_update_limit_insert
  BEFORE UPDATE OR DELETE OR INSERT ON transactions
  FOR EACH ROW
  EXECUTE FUNCTION transactions_block_delete_update_limit_insert();



-- ======================== change_history ========================
CREATE TABLE IF NOT EXISTS change_history (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  changes       jsonb DEFAULT '[]'::jsonb,
  performed_by  uuid NOT NULL REFERENCES employees(id) ON DELETE RESTRICT,
  occurred_at   timestamptz NOT NULL DEFAULT now()
);



-- ======================== undo_change_history ========================
CREATE TABLE IF NOT EXISTS undo_change_history (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  change_history_id   uuid NOT NULL REFERENCES change_history(id) ON DELETE CASCADE,
  occurred_at         timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS unique_index_undo_change_history_change_history_id ON undo_change_history (change_history_id);



-- -- update these:

-- development values
-- make sure to delete this !!!
-- employees, users, products, product_images, events, booths,
-- employee_event_booth_roles, product_event_prices,
-- event_product_booth_link, wallets, transactions

INSERT INTO employees (id, username, email, password_hash, is_admin, created_by, deleted_at)
VALUES 
('10000000000000000000000000000001', 'development_admin1', 'email_admin@gmail.com', '$argon2id$v=19$m=65536,t=3,p=2$HaqrwxL5kzBuWb6s+GVqKg$PmUeF6KsUupww8J9JT/Wpea73/wqqvpMAxnF/z7hFxo', TRUE, NULL, NULL),
('10000000000000000000000000000002', 'development_admin2', 'email_admin2@gmail.com', '$argon2id$v=19$m=65536,t=3,p=2$HaqrwxL5kzBuWb6s+GVqKg$PmUeF6KsUupww8J9JT/Wpea73/wqqvpMAxnF/z7hFxo', TRUE, NULL, NULL),

('10000000000000000000000000000003', 'development_event1_manager1', 'email_event_manager@gmail.com', '$argon2id$v=19$m=65536,t=3,p=2$HaqrwxL5kzBuWb6s+GVqKg$PmUeF6KsUupww8J9JT/Wpea73/wqqvpMAxnF/z7hFxo', FALSE, '10000000000000000000000000000001', NULL),
('10000000000000000000000000000004', 'development_event1_manager2', 'email_event_manager2@gmail.com', '$argon2id$v=19$m=65536,t=3,p=2$HaqrwxL5kzBuWb6s+GVqKg$PmUeF6KsUupww8J9JT/Wpea73/wqqvpMAxnF/z7hFxo', FALSE, '10000000000000000000000000000002', NULL),
('10000000000000000000000000000005', 'development_event3_manager1', 'email_event3_manager@gmail.com', '$argon2id$v=19$m=65536,t=3,p=2$HaqrwxL5kzBuWb6s+GVqKg$PmUeF6KsUupww8J9JT/Wpea73/wqqvpMAxnF/z7hFxo', FALSE, '10000000000000000000000000000001', NULL),

('10000000000000000000000000000006', 'development_event1_booth1_cashier1', 'email_event_cashier@gmail.com', '$argon2id$v=19$m=65536,t=3,p=2$HaqrwxL5kzBuWb6s+GVqKg$PmUeF6KsUupww8J9JT/Wpea73/wqqvpMAxnF/z7hFxo', FALSE, '10000000000000000000000000000001', NULL),
('10000000000000000000000000000007', 'development_event1_booth1_2_cashier1', 'email_event_cashier2@gmail.com', '$argon2id$v=19$m=65536,t=3,p=2$HaqrwxL5kzBuWb6s+GVqKg$PmUeF6KsUupww8J9JT/Wpea73/wqqvpMAxnF/z7hFxo', FALSE, '10000000000000000000000000000001', NULL),
('10000000000000000000000000000008', 'development_event1_2_booth1_cashier1', 'email_event1_2_cashier@gmail.com', '$argon2id$v=19$m=65536,t=3,p=2$HaqrwxL5kzBuWb6s+GVqKg$PmUeF6KsUupww8J9JT/Wpea73/wqqvpMAxnF/z7hFxo', FALSE, '10000000000000000000000000000001', NULL),

('10000000000000000000000000000009', 'development_event1_booth1_seller1', 'email_event_seller@gmail.com', '$argon2id$v=19$m=65536,t=3,p=2$HaqrwxL5kzBuWb6s+GVqKg$PmUeF6KsUupww8J9JT/Wpea73/wqqvpMAxnF/z7hFxo', FALSE, '10000000000000000000000000000001', NULL),
('10000000000000000000000000000010', 'development_event1_booth1_seller2', 'email_event_seller2@gmail.com', '$argon2id$v=19$m=65536,t=3,p=2$HaqrwxL5kzBuWb6s+GVqKg$PmUeF6KsUupww8J9JT/Wpea73/wqqvpMAxnF/z7hFxo', FALSE, '10000000000000000000000000000001', NULL),
('10000000000000000000000000000011', 'development_event1_booth3_4_seller1', 'email_event1_2_seller@gmail.com', '$argon2id$v=19$m=65536,t=3,p=2$HaqrwxL5kzBuWb6s+GVqKg$PmUeF6KsUupww8J9JT/Wpea73/wqqvpMAxnF/z7hFxo', FALSE, '10000000000000000000000000000001', NULL),
('10000000000000000000000000000012', 'development_event2_booth1_seller1', 'email_event2_seller@gmail.com', '$argon2id$v=19$m=65536,t=3,p=2$HaqrwxL5kzBuWb6s+GVqKg$PmUeF6KsUupww8J9JT/Wpea73/wqqvpMAxnF/z7hFxo', FALSE, '10000000000000000000000000000001', NULL),

('10000000000000000000000000000013', 'development_event1_booth1_seller1_cashier1', 'email_event1_booth1_seller1_cashier1@gmail.com', '$argon2id$v=19$m=65536,t=3,p=2$HaqrwxL5kzBuWb6s+GVqKg$PmUeF6KsUupww8J9JT/Wpea73/wqqvpMAxnF/z7hFxo', FALSE, '10000000000000000000000000000001', NULL),

('10000000000000000000000000000014', 'development_admin_deleted', 'email_admin_deleted@gmail.com', '$argon2id$v=19$m=65536,t=3,p=2$HaqrwxL5kzBuWb6s+GVqKg$PmUeF6KsUupww8J9JT/Wpea73/wqqvpMAxnF/z7hFxo', TRUE, NULL, '2025-10-16 20:58:08.485849+0'),
('10000000000000000000000000000015', 'development_event_manager_deleted', 'email_event_manager_deleted@gmail.com', '$argon2id$v=19$m=65536,t=3,p=2$HaqrwxL5kzBuWb6s+GVqKg$PmUeF6KsUupww8J9JT/Wpea73/wqqvpMAxnF/z7hFxo', FALSE, '10000000000000000000000000000001', '2025-10-16 20:58:08.485849+0'),
('10000000000000000000000000000016', 'development_cashier_deleted', 'email_cashier_deleted@gmail.com', '$argon2id$v=19$m=65536,t=3,p=2$HaqrwxL5kzBuWb6s+GVqKg$PmUeF6KsUupww8J9JT/Wpea73/wqqvpMAxnF/z7hFxo', FALSE, '10000000000000000000000000000001', '2025-10-16 20:58:08.485849+0');

INSERT INTO employees (id, created_at, username, email, password_hash, is_admin, created_by, deleted_at)
VALUES 
('10000000000000000000000000000017', '2023-1-1 11:11:54.767705+01','development_seller_old1', 'development_seller_old@gmail.com', '$argon2id$v=19$m=65536,t=3,p=2$HaqrwxL5kzBuWb6s+GVqKg$PmUeF6KsUupww8J9JT/Wpea73/wqqvpMAxnF/z7hFxo', FALSE, '10000000000000000000000000000001', NULL),
('10000000000000000000000000000018', '2023-12-30 11:11:54.767705+01','development_seller_old2', 'development_seller_old2@gmail.com', '$argon2id$v=19$m=65536,t=3,p=2$HaqrwxL5kzBuWb6s+GVqKg$PmUeF6KsUupww8J9JT/Wpea73/wqqvpMAxnF/z7hFxo', FALSE, '10000000000000000000000000000001', NULL),
('10000000000000000000000000000019', '2027-1-1 11:11:54.767705+01','development_seller_future1', 'development_seller_future1@gmail.com', '$argon2id$v=19$m=65536,t=3,p=2$HaqrwxL5kzBuWb6s+GVqKg$PmUeF6KsUupww8J9JT/Wpea73/wqqvpMAxnF/z7hFxo', FALSE, '10000000000000000000000000000001', NULL),
('10000000000000000000000000000020', '2027-12-30 11:11:54.767705+01','development_seller_future2', 'development_seller_future2@gmail.com', '$argon2id$v=19$m=65536,t=3,p=2$HaqrwxL5kzBuWb6s+GVqKg$PmUeF6KsUupww8J9JT/Wpea73/wqqvpMAxnF/z7hFxo', FALSE, '10000000000000000000000000000001', NULL);

INSERT INTO events (id, name, start_at, end_at, created_by)
VALUES
('30000000000000000000000000000001', 'development_event1', '2025-8-16 20:40:55+00:00', '2026-11-16 20:40:55+00:00', '10000000000000000000000000000001'),
('30000000000000000000000000000002', 'development_event2', '2025-9-16 20:40:55+00:00', '2026-10-16 20:40:55+00:00', '10000000000000000000000000000001'),
('30000000000000000000000000000003', 'development_event3', '2025-10-16 20:40:55+00:00', '2026-9-16 20:40:55+00:00', '10000000000000000000000000000001'),
('30000000000000000000000000000004', 'development_future_event', '2026-12-16 20:40:55+00:00', '2027-11-16 20:40:55+00:00', '10000000000000000000000000000001'),
('30000000000000000000000000000005', 'development_past_event', '2023-10-16 20:40:55+00:00', now() + INTERVAL '2 seconds', '10000000000000000000000000000001'),
('30000000000000000000000000000006', 'adevelopment_future_event', '2026-11-16 20:40:55+00:00', '2027-12-16 20:40:55+00:00', '10000000000000000000000000000001'),
('30000000000000000000000000000007', 'adevelopment_past_event', '2023-9-16 20:40:55+00:00', now() + INTERVAL '4 seconds', '10000000000000000000000000000001');

INSERT INTO events (id, name, start_at, end_at, created_by, deleted_at)
VALUES
('30000000000000000000000000000008', 'development_event_deleted', '2025-8-16 20:40:55+00:00', '2026-11-16 20:40:55+00:00', '10000000000000000000000000000001', now());

INSERT INTO booths (id, name, event_id, booth_type, created_by)
VALUES
('40000000000000000000000000000001', 'development_booth1_event1_cashier', '30000000000000000000000000000001', 'cashier', '10000000000000000000000000000001'),
('40000000000000000000000000000002', 'development_booth2_event1_cashier', '30000000000000000000000000000001', 'cashier', '10000000000000000000000000000001'),

('40000000000000000000000000000003', 'development_booth1_event1_seller', '30000000000000000000000000000001', 'seller', '10000000000000000000000000000001'),
('40000000000000000000000000000004', 'development_booth2_event1_seller', '30000000000000000000000000000001', 'seller', '10000000000000000000000000000001'),
('40000000000000000000000000000005', 'development_booth3_event1_seller', '30000000000000000000000000000001', 'seller', '10000000000000000000000000000001'),
('40000000000000000000000000000006', 'development_booth4_event1_seller', '30000000000000000000000000000001', 'seller', '10000000000000000000000000000001'),

('40000000000000000000000000000007', 'development_booth1_event2_cashier', '30000000000000000000000000000002', 'cashier', '10000000000000000000000000000001'),

('40000000000000000000000000000008', 'development_booth1_event2_seller', '30000000000000000000000000000002', 'seller', '10000000000000000000000000000001');

INSERT INTO booths (id, name, event_id, booth_type, created_by, deleted_at)
VALUES
('40000000000000000000000000000009', 'development_booth_event1_deleted', '30000000000000000000000000000001', 'seller', '10000000000000000000000000000001', now());

INSERT INTO product_images (id, image_path, image_filename, image_mime_type, image_size_bytes, image_width, image_height)
VALUES
('02000000000000000000000000000001', 'hamburger1.png', 'hamburger1.png', 'image/png', 54289, 225, 225),
('02000000000000000000000000000002', 'hamburger2.png', 'hamburger2.png', 'image/png', 1882222, 1500, 1125),
('02000000000000000000000000000003', 'hamburger3.png', 'hamburger3.png', 'image/png', 5308416, 1440, 2465),
('02000000000000000000000000000004', 'kofola.png', 'kofola.png', 'image/png', 163383, 250, 333),
('02000000000000000000000000000005', 'rohlik.png', 'rohlik.png', 'image/png', 53810, 250, 177);

INSERT INTO products (id, event_id, name, price, image_id)
VALUES
('20000000000000000000000000000001', '30000000000000000000000000000001', 'event1_2000_booth1', 2000, '02000000000000000000000000000001'),
('20000000000000000000000000000003', '30000000000000000000000000000001', 'event1_7_booth1 imageless', 7, '02000000000000000000000000000002'),
('20000000000000000000000000000004', '30000000000000000000000000000001', 'event1_10000_booth2', 10000, '02000000000000000000000000000003'),
('20000000000000000000000000000005', '30000000000000000000000000000001', 'event1_345_booth1_2_kofola', 345, '02000000000000000000000000000004'),
('20000000000000000000000000000006', '30000000000000000000000000000002', 'event2_123_booth1_rohlík', 123, '02000000000000000000000000000005'),
('20000000000000000000000000000007', '30000000000000000000000000000001', 'event1_11111_2_22222_booth1', 11111, '02000000000000000000000000000002'),
('20000000000000000000000000000008', '30000000000000000000000000000002', 'event1_11111_2_22222_booth1', 22222, '02000000000000000000000000000002'),
('20000000000000000000000000000002', '30000000000000000000000000000001', 'event1_2147483647_booth1aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 2147483647, NULL),
('20000000000000000000000000000009', '30000000000000000000000000000001', 'hamburger 2', 5, NULL),
('20000000000000000000000000000010', '30000000000000000000000000000001', 'Hamburger 3', 6, NULL);

INSERT INTO product_booth_link (product_id, booth_id)
VALUES
('20000000000000000000000000000001', '40000000000000000000000000000003'),
('20000000000000000000000000000002', '40000000000000000000000000000003'),
('20000000000000000000000000000003', '40000000000000000000000000000003'),
('20000000000000000000000000000004', '40000000000000000000000000000004'),
('20000000000000000000000000000005', '40000000000000000000000000000003'),
('20000000000000000000000000000005', '40000000000000000000000000000004'),
('20000000000000000000000000000006', '40000000000000000000000000000008'),
('20000000000000000000000000000007', '40000000000000000000000000000003'),
('20000000000000000000000000000008', '40000000000000000000000000000008');

INSERT INTO categories (id, name, event_id)
VALUES
('90000000000000000000000000000001', 'Jídlo', '30000000000000000000000000000001'),
('90000000000000000000000000000002', 'Hamburger', '30000000000000000000000000000001'),
('90000000000000000000000000000003', 'Pití', '30000000000000000000000000000001'),
('90000000000000000000000000000004', 'Pečivo', '30000000000000000000000000000001'),
('90000000000000000000000000000005', 'Jídlo', '30000000000000000000000000000002');

INSERT INTO category_booth_link (category_id, booth_id)
VALUES
('90000000000000000000000000000001', '40000000000000000000000000000003'),
('90000000000000000000000000000001', '40000000000000000000000000000004'),
('90000000000000000000000000000002', '40000000000000000000000000000003'),
('90000000000000000000000000000003', '40000000000000000000000000000003'),
('90000000000000000000000000000004', '40000000000000000000000000000003'),
('90000000000000000000000000000005', '40000000000000000000000000000008');

INSERT INTO category_product_link (category_id, product_id)
VALUES
('90000000000000000000000000000001', '20000000000000000000000000000001'),
('90000000000000000000000000000001', '20000000000000000000000000000003'),
('90000000000000000000000000000002', '20000000000000000000000000000001'),
('90000000000000000000000000000003', '20000000000000000000000000000005'),
('90000000000000000000000000000005', '20000000000000000000000000000006');

INSERT INTO employee_event_booth_roles (id, employee_id, event_id, booth_id)
VALUES
('50000000000000000000000000000001', '10000000000000000000000000000003', '30000000000000000000000000000001', NULL),
('50000000000000000000000000000002', '10000000000000000000000000000004', '30000000000000000000000000000001', NULL),
('50000000000000000000000000000003', '10000000000000000000000000000005', '30000000000000000000000000000003', NULL),

('50000000000000000000000000000004', '10000000000000000000000000000006', '30000000000000000000000000000001', '40000000000000000000000000000001'),
('50000000000000000000000000000005', '10000000000000000000000000000007', '30000000000000000000000000000001', '40000000000000000000000000000001'),
('50000000000000000000000000000006', '10000000000000000000000000000007', '30000000000000000000000000000001', '40000000000000000000000000000002'),
('50000000000000000000000000000007', '10000000000000000000000000000008', '30000000000000000000000000000001', '40000000000000000000000000000001'),
('50000000000000000000000000000008', '10000000000000000000000000000008', '30000000000000000000000000000002', '40000000000000000000000000000007'),

('50000000000000000000000000000009', '10000000000000000000000000000009', '30000000000000000000000000000001', '40000000000000000000000000000003'),
('50000000000000000000000000000010', '10000000000000000000000000000010', '30000000000000000000000000000001', '40000000000000000000000000000003'),
('50000000000000000000000000000011', '10000000000000000000000000000011', '30000000000000000000000000000001', '40000000000000000000000000000005'),
('50000000000000000000000000000012', '10000000000000000000000000000011', '30000000000000000000000000000001', '40000000000000000000000000000006'),
('50000000000000000000000000000013', '10000000000000000000000000000012', '30000000000000000000000000000002', '40000000000000000000000000000008'),

('50000000000000000000000000000014', '10000000000000000000000000000013', '30000000000000000000000000000001', '40000000000000000000000000000003'),
('50000000000000000000000000000015', '10000000000000000000000000000013', '30000000000000000000000000000001', '40000000000000000000000000000001');

INSERT INTO users (id, first_name, last_name, email, phone_number, other_identifier)
VALUES 
('01000000000000000000000000000001', 'Pavel_ev1', 'Struhař', 'pavel.struhar@gmail.com', '+420123456789', NULL),
('01000000000000000000000000000002', 'jiRka_ev1', 'PAvel  ', 'jirkA@gmail.com', NULL, NULL),
('01000000000000000000000000000003', 'ev_1', 'ev_1  ', 'ev_1@gmail.com', NULL, NULL),
('01000000000000000000000000000004', 'ev_2', 'ev_2  ', 'ev_2@gmail.com', NULL, NULL),
('01000000000000000000000000000005', 'ev_1_2', 'ev_1_2  ', 'ev_1_2@gmail.com', NULL, NULL);
  
INSERT INTO wallets (id, event_id, tag_id, owner_id, balance_czk, created_by)
VALUES
('80000000000000000000000000000001', '30000000000000000000000000000001', '00A713A700000000','01000000000000000000000000000001', 99999, '10000000000000000000000000000003'),
('80000000000000000000000000000002', '30000000000000000000000000000001', 'jiRka_ev1','01000000000000000000000000000002', 21, '10000000000000000000000000000003'),
('80000000000000000000000000000003', '30000000000000000000000000000001', 'ev_1','01000000000000000000000000000003', 0, '10000000000000000000000000000003'),
('80000000000000000000000000000004', '30000000000000000000000000000002', 'ev_2','01000000000000000000000000000004', 9348, '10000000000000000000000000000003'),
('80000000000000000000000000000005', '30000000000000000000000000000001', '005AC02800000000','01000000000000000000000000000005', 111, '10000000000000000000000000000003'),
('80000000000000000000000000000006', '30000000000000000000000000000002', '005AC02800000000','01000000000000000000000000000005', 222, '10000000000000000000000000000003');


-- maybe?
-- maybe add indexes for frequently queried columns:
-- CREATE INDEX ix_transactions_tag_occurred_at ON transactions (tag_id, occurred_at DESC);
-- CREATE INDEX ix_transactions_account_occurred_at ON transactions (account_id, occurred_at DESC);
-- transactions (performed_by, occurred_at DESC)
-- consider event_id indexes.
