CREATE EXTENSION IF NOT EXISTS pgcrypto; -- pro gen_random_uuid()
-- CREATE EXTENSION IF NOT EXISTS citext; -- case-insensitive text


-- make sure all the trigger constraints work (in tests?)



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
  email             text,
  phone_number      text, -- +[country code][number] (CZ: +420123456789) E.164 format
  other_identifier  text,
  created_at        timestamptz NOT NULL DEFAULT now(),
  deleted_at        timestamptz, -- NULL -> existuje, NOT NULL -> smazáno
  CONSTRAINT valid_phone_number_check
    CHECK (phone_number ~ '^\+[1-9]\d{0,14}$')
);
CREATE UNIQUE INDEX IF NOT EXISTS unique_index_users_names_email_phone_identifier
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



CREATE OR REPLACE FUNCTION sessions_update_modified_at()
RETURNS trigger AS $$
BEGIN
  NEW.modified_at := now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_sessions_update_modified_at
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
-- seller: může dělat payments/refunds
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
  products_info     jsonb DEFAULT '[]'::jsonb, -- id (product mohl být smazán/upraven), price, name, quantity 
  refunded_transaction_id uuid REFERENCES transactions(id) ON DELETE RESTRICT,

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
--  - u refund kontroluje, že má refunded_transaction_id, ta transakce je payment a není již refundována
--    a automaticky nastaví amount_czk, products_info, tag_id, wallet_id, user_id z refundované transakce
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
  refunded_tx_type text;
  refunded_tx_amount int;
  refunded_tx_products jsonb;
  refunded_tx_tag_id text;
  refunded_tx_wallet_id uuid;
  refunded_tx_user_id uuid;
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


    -- refund: zamkne řádek refundované transakce, zkontroluje, a automaticky nastaví hodnoty
    IF NEW.transaction_type = 'refund' THEN
      IF NEW.refunded_transaction_id IS NULL THEN
        RAISE EXCEPTION 'refund must reference a transaction via refunded_transaction_id';
      END IF;

      -- zamkne řádek refundované transakce (zabrání souběžným refundům)
      SELECT transaction_type, amount_czk, products_info, tag_id, wallet_id, user_id
        INTO refunded_tx_type, refunded_tx_amount, refunded_tx_products, refunded_tx_tag_id, refunded_tx_wallet_id, refunded_tx_user_id
        FROM transactions
        WHERE id = NEW.refunded_transaction_id
        FOR UPDATE;

      IF NOT FOUND THEN
        RAISE EXCEPTION 'refunded transaction % does not exist', NEW.refunded_transaction_id;
      END IF;

      IF refunded_tx_type != 'payment' THEN
        RAISE EXCEPTION 'refunded transaction % is not a payment', NEW.refunded_transaction_id;
      END IF;

      PERFORM 1
        FROM transactions
        WHERE refunded_transaction_id = NEW.refunded_transaction_id;

      IF FOUND THEN
        RAISE EXCEPTION 'transaction % has already been refunded', NEW.refunded_transaction_id;
      END IF;

      -- automaticky nastaví hodnoty z refundované transakce
      NEW.amount_czk := -refunded_tx_amount;
      NEW.products_info := refunded_tx_products;
      NEW.tag_id := refunded_tx_tag_id;
      NEW.wallet_id := refunded_tx_wallet_id;
      NEW.user_id := refunded_tx_user_id;
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



-- Transactions: queries filter by wallet_id, booth_id, event_id, transaction_type, occurred_at
CREATE INDEX IF NOT EXISTS idx_transactions_wallet_id ON transactions (wallet_id);
CREATE INDEX IF NOT EXISTS idx_transactions_event_id_occurred_at ON transactions (event_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_booth_id ON transactions (booth_id);

-- Wallets: frequently queried by (event_id, tag_id) and (owner_id)
CREATE INDEX IF NOT EXISTS idx_wallets_owner_id ON wallets (owner_id) WHERE deleted_at IS NULL;

-- Employee roles: frequently queried by employee_id, event_id
CREATE INDEX IF NOT EXISTS idx_employee_event_booth_roles_employee_id ON employee_event_booth_roles (employee_id);
CREATE INDEX IF NOT EXISTS idx_employee_event_booth_roles_event_id ON employee_event_booth_roles (event_id);

-- Products, categories, booths: by event_id (used in almost every query)
CREATE INDEX IF NOT EXISTS idx_products_event_id ON products (event_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_categories_event_id ON categories (event_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_booths_event_id ON booths (event_id) WHERE deleted_at IS NULL;

-- Sessions: for cleanup job
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions (expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_sessions_employee_id ON sessions (employee_id);

-- Change history: for undo/redo queries
CREATE INDEX IF NOT EXISTS idx_change_history_performed_by_occurred_at ON change_history (performed_by, occurred_at DESC);
